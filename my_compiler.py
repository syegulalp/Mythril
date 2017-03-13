from ctypes import CFUNCTYPE
from ctypes import c_void_p
from llvmlite import ir
import llvmlite.binding as llvm
from my_builtin_functions import define_printd
from my_builtin_functions import define_printb
from my_visitor import NodeVisitor
from my_ast import Num, Var
from my_ast import VarDecl
from my_ast import FuncCall
from my_grammar import *

RET_VAR = 'ret_var'
INT8 = 'int8'
INT32 = 'int32'
# TODO: temorarily making Decimal a DoubleType till find (or make) a better representation
type_map = {BOOL: lambda: ir.IntType(1), INT: lambda: ir.IntType(64), INT8: lambda: ir.IntType(8), INT32: lambda: ir.IntType(32), DEC: ir.DoubleType, FLOAT: ir.FloatType, FUNC: ir.FunctionType, VOID: ir.VoidType}


class CodeGenerator(NodeVisitor):
	def __init__(self, file_name):
		super().__init__()
		self.file_name = file_name
		self.module = ir.Module()
		func_ty = ir.FunctionType(ir.VoidType(), [])
		func = ir.Function(self.module, func_ty, '__main__')
		entry_block = func.append_basic_block('entry')
		self.function = func
		self.main_function = func
		self.builder = ir.IRBuilder(entry_block)
		self.main_builder = self.builder
		self.exit_block = None
		llvm.initialize()
		llvm.initialize_native_target()
		llvm.initialize_native_asmprinter()
		self.target = llvm.Target.from_default_triple()
		self._add_builtins()

	def visit_program(self, node):
		self.visit(node.block)
		self.builder.ret_void()

	@staticmethod
	def visit_num(node):
		return ir.Constant(type_map[node.token.value_type](), node.value)

	def visit_var(self, node):
		return self.load(node.value)

	def visit_binop(self, node):
		op = node.op.value
		left = self.visit(node.left)
		right = self.visit(node.right)
		if isinstance(left.type, ir.IntType):
			if op == PLUS:
				return self.builder.add(left, right, 'addtmp')
			elif op == MINUS:
				return self.builder.sub(left, right, 'subtmp')
			elif op == MUL:
				return self.builder.mul(left, right, 'multmp')
			elif op == FLOORDIV:
				return self.builder.sdiv(left, right, 'divtmp')
			elif op == DIV:
				return self.builder.fdiv(self.builder.sitofp(left, type_map[DEC]()), self.builder.sitofp(right, type_map[DEC]()), 'fdivtmp')
			elif op == MOD:
				return self.builder.srem(left, right, 'modtmp')
			elif op == POWER:
				temp = self.builder.alloca(type_map[INT]())
				self.builder.store(left, temp)
				for _ in range(node.right.value - 1):
					res = self.builder.mul(self.builder.load(temp), left)
					self.builder.store(res, temp)
				return self.builder.load(temp)
			elif op == AND:
				return self.builder.and_(left, right)
			elif op == OR:
				return self.builder.or_(left, right)
			elif op == XOR:
				return self.builder.xor(left, right)
			elif op == ARITHMATIC_LEFT_SHIFT or op == BINARY_LEFT_SHIFT:
				return self.builder.shl(left, right)
			elif op == ARITHMATIC_RIGHT_SHIFT:
				return self.builder.ashr(left, right)
			elif op == BINARY_LEFT_SHIFT:
				return self.builder.lshr(left, right)
			elif op in (EQUALS, NOT_EQUALS, LESS_THAN, LESS_THAN_OR_EQUAL_TO, GREATER_THAN, GREATER_THAN_OR_EQUAL_TO):
				cmp = self.builder.icmp_signed(op, left, right, 'cmptmp')
				return self.builder.uitofp(cmp, type_map[BOOL](), 'booltmp')
			else:
				raise SyntaxError('Unknown binary operator', node.op)
		else:
			if op == PLUS:
				return self.builder.fadd(left, right, 'faddtmp')
			elif op == MINUS:
				return self.builder.fsub(left, right, 'fsubtmp')
			elif op == MUL:
				return self.builder.fmul(left, right, 'fmultmp')
			elif op == FLOORDIV:
				return self.builder.udiv(self.builder.fptosi(left, ir.IntType(64)), self.builder.fptosi(right, ir.IntType(64)), 'ffloordivtmp')
			elif op == DIV:
				return self.builder.fdiv(left, right, 'fdivtmp')
			elif op == MOD:
				return self.builder.frem(left, right, 'fmodtmp')
			elif op == POWER:
				temp = self.builder.alloca(type_map[DEC]())
				self.builder.store(left, temp)
				for _ in range(node.right.value - 1):
					res = self.builder.fmul(self.builder.load(temp), left)
					self.builder.store(res, temp)
				return self.builder.load(temp)
			elif op in (EQUALS, NOT_EQUALS, LESS_THAN, LESS_THAN_OR_EQUAL_TO, GREATER_THAN, GREATER_THAN_OR_EQUAL_TO):
				cmp = self.builder.fcmp_ordered(op, left, right, 'cmptmp')
				return self.builder.sitofp(cmp, type_map[BOOL](), 'booltmp')
			else:
				raise SyntaxError('Unknown binary operator', node.op)
		# 	elif op == CAST:
		# 		cast_type = node.right.value
		# 		if cast_type == INT:
		# 			return int(left)
		# 		elif cast_type == DEC:
		# 			return Decimal(left)
		# 		elif cast_type == FLOAT:
		# 			return float(left)
		# 		elif cast_type == COMPLEX:
		# 			return complex(left)
		# 		elif cast_type == STR:
		# 			return str(left)
		# 		elif cast_type == BOOL:
		# 			return bool(left)
		# 		elif cast_type == BYTES:
		# 			return bytes(left)
		# 		elif cast_type == LIST:
		# 			return list(left)
		# 		elif cast_type == TUPLE:
		# 			return tuple(left)
		# 		elif cast_type == DICT:
		# 			return dict(left)
		# 		elif cast_type == ENUM:
		# 			return Enum(left.value, left)
		# 		elif cast_type in (ANY, FUNC, NULL):
		# 			raise TypeError('file={} line={}: Cannot cast to type {}'.format(self.file_name, node.line_num, cast_type))

	def visit_funcdecl(self, node):
		self.start_function(node.name.value, node.return_type, node.parameters, node.parameter_defaults, node.varargs)
		for i, arg in enumerate(self.function.args):
			arg.name = list(node.parameters.keys())[i]
			var_addr = self.builder.alloca(arg.type, name=arg.name)
			self.define(arg.name, var_addr)
			self.builder.store(arg, var_addr)
		if self.function.function_type.return_type != type_map[VOID]():
			ret_var_addr = self.builder.alloca(self.function.function_type.return_type, name=RET_VAR)
			self.define(RET_VAR, ret_var_addr)
		ret = self.visit(node.body)
		self.end_function(ret)
		return self.function

	def visit_funccall(self, node):
		func_type = self.search_scopes(node.name.value)
		if len(node.arguments) < len(func_type.args):
			args = []
			args_supplied = []
			for x, arg in enumerate(func_type.arg_order):
				if x < len(node.arguments):
					args.append(self.visit(node.arguments[x]))
				else:
					if node.named_arguments and arg in node.named_arguments:
						args.append(self.visit(node.named_arguments[arg]))
					else:
						if set(node.named_arguments.keys()) & set(args_supplied):
							raise TypeError('got multiple values for argument(s) {}'.format(set(node.named_arguments.keys()) & set(args_supplied)))
						args.append(self.visit(func_type.parameter_defaults[arg]))
				args_supplied.append(arg)
		elif len(node.arguments) + len(node.named_arguments) > len(func_type.args):
			raise SyntaxError('Unexpected arguments')
		else:
			args = [self.visit(arg) for arg in node.arguments]
		return self.call(node.name.value, args)

	def visit_compound(self, node):
		ret = None
		for child in node.children:
			temp = self.visit(child)
			if temp:
				ret = temp
		return ret

	def visit_typedeclaration(self, node):
		raise NotImplementedError

	def visit_vardecl(self, node):
		var_addr = self.builder.alloca(type_map[node.type_node.value](), name=node.var_node.value)
		self.define(node.var_node.value, var_addr)
		self.store(self.visit(node.var_node), node.var_node.value)

	def visit_type(self, node):
		raise NotImplementedError

	def visit_noop(self, node):
		pass

	def visit_if(self, node):
		func_exit = self.exit_block
		if_end = self.add_block('if_end')
		self.exit_block = if_end
		for x, comp in enumerate(node.comps):
			cond_val = self.visit(comp)
			with self.builder.if_then(cond_val):
				ret = self.visit(node.blocks[x])
				if not ret:
					self.branch(if_end)
		self.branch(if_end)
		self.position_at_end(if_end)
		self.exit_block = func_exit

	def visit_else(self, _):
		return self.builder.icmp_unsigned(EQUALS, self.const(1), self.const(1), 'cmptmp')

	def visit_while(self, node):
		raise NotImplementedError

	def visit_for(self, node):
		init_block = self.add_block('for.init')
		test_block = self.add_block('for.cond')
		body_block = self.add_block('for.body')
		end_block = self.add_block('for.end')
		self.branch(init_block)
		self.position_at_end(init_block)
		loop_range = self.visit(node.iterator)
		start = self.const(loop_range[0])
		stop = self.const(loop_range[-1])
		step = self.const(1)
		varname = node.elements[0].value
		self.allocate(start, varname, type_map[INT]())
		self.branch(test_block)
		self.position_at_end(test_block)
		cond = self.builder.icmp_unsigned(LESS_THAN_OR_EQUAL_TO, self.load(varname), stop)
		self.cbranch(cond, body_block, end_block)
		self.position_at_end(body_block)
		self.visit(node.block)
		succ = self.builder.add(step, self.load(varname))
		self.store(varname, succ)
		self.branch(test_block)
		self.position_at_end(end_block)

	def visit_loopblock(self, node):
		for child in node.children:
			temp = self.visit(child)
			if temp == CONTINUE or temp == BREAK:
				return temp

	def visit_switch(self, node):
		default_exists = False
		switch_end_block = self.add_block('switch_end')
		default_block = self.add_block('default')
		switch = self.switch(self.visit(node.value), default_block)
		cases = []
		for case in node.cases:
			if case.value == DEFAULT:
				cases.append(default_block)
				default_exists = True
			else:
				cases.append(self.add_block('case'))
		if not default_exists:
			self.position_at_start(default_block)
			self.branch(switch_end_block)
		for x, case in enumerate(node.cases):
			self.position_at_start(cases[x])
			break_ = self.visit(case.block)
			if break_ == BREAK:
				self.branch(switch_end_block)
			else:
				if x == len(node.cases) - 1:
					self.branch(switch_end_block)
				else:
					self.branch(cases[x + 1])
			if case.value != DEFAULT:
				switch.add_case(self.visit(case.value), cases[x])
		self.position_at_end(switch_end_block)
		return switch

	def visit_case(self, node):
		raise NotImplementedError

	@staticmethod
	def visit_break(_):
		return BREAK

	@staticmethod
	def visit_continue(_):
		return CONTINUE

	@staticmethod
	def visit_pass(_):
		return

	def visit_unaryop(self, node):
		op = node.op.value
		expr = self.visit(node.expr)
		if op == PLUS:
			return expr
		elif op == MINUS:
			return self.builder.neg(expr)
		elif op == NOT:
			return self.builder.not_(expr)

	def visit_range(self, node):
		left = self.visit(node.left)
		right = self.visit(node.right)
		return range(left.constant, right.constant)

	def visit_assign(self, node):
		var = self.visit(node.right)
		if isinstance(node.left, VarDecl):
			var_name = node.left.var_node.value
			if node.left.type_node.value == FLOAT:
				node.right.value = float(node.right.value)
			self.allocate(var, var_name, var.type)
		else:
			var_name = node.left.value
			var_value = self.top_scope.get(var_name)
			if var_value:
				if isinstance(var_value, float):
					node.right.value = float(node.right.value)
				self.store(var_name, var)
			else:
				self.allocate(var, var_name, var.type)

	def visit_opassign(self, node):
		var_name = node.left.value
		op = node.op.value
		right = self.visit(node.right)
		if isinstance(self.search_scopes(var_name).type.pointee, ir.IntType):
			if op == PLUS_ASSIGN:
				res = self.builder.add(self.load(var_name), right)
			elif op == MINUS_ASSIGN:
				res = self.builder.sub(self.load(var_name), right)
			elif op == MUL_ASSIGN:
				res = self.builder.mul(self.load(var_name), right)
			elif op == FLOORDIV_ASSIGN:
				res = self.builder.sdiv(self.load(var_name), right)
			elif op == DIV_ASSIGN:
				res = self.builder.fdiv(self.load(var_name), right)
			elif op == MOD_ASSIGN:
				res = self.builder.srem(self.load(var_name), right)
			elif op == POWER_ASSIGN:
				temp = self.builder.alloca(type_map[INT]())
				self.builder.store(self.load(var_name), temp)
				for _ in range(node.right.value - 1):
					res = self.builder.mul(self.builder.load(temp), self.load(var_name))
					self.builder.store(res, temp)
				res = self.builder.load(temp)
			else:
				raise NotImplementedError()
		else:
			if op == PLUS_ASSIGN:
				res = self.builder.fadd(self.load(var_name), right)
			elif op == MINUS_ASSIGN:
				res = self.builder.fsub(self.load(var_name), right)
			elif op == MUL_ASSIGN:
				res = self.builder.fmul(self.load(var_name), right)
			elif op == FLOORDIV_ASSIGN:
				res = self.builder.sdiv(self.builder.fptosi(self.load(var_name), ir.IntType(64)), self.builder.fptosi(right, ir.IntType(64)))
			elif op == DIV_ASSIGN:
				res = self.builder.fdiv(self.load(var_name), right)
			elif op == MOD_ASSIGN:
				res = self.builder.frem(self.load(var_name), right)
			elif op == POWER_ASSIGN:
				temp = self.builder.alloca(type_map[DEC]())
				self.builder.store(self.load(var_name), temp)
				for _ in range(node.right.value - 1):
					res = self.builder.fmul(self.builder.load(temp), self.load(var_name))
					self.builder.store(res, temp)
				res = self.builder.load(temp)
			else:
				raise NotImplementedError()
		self.store(var_name, res)

	def visit_anonymousfunc(self, node):
		raise NotImplementedError

	def visit_return(self, node):
		val = self.visit(node.value)
		if val.type != ir.VoidType():
			self.store(RET_VAR, val)
		self.branch(self.exit_block)
		return True

	def visit_constant(self, node):
		if node.value == TRUE:
			return self.const(1, 1)
		elif node.value == FALSE:
			return self.const(0, 1)
		else:
			raise NotImplementedError('file={} line={}'.format(self.file_name, node.line_num))

	def visit_str(self, node):
		return self.stringz(node.value)

	def visit_collection(self, node):
		raise NotImplementedError

	def visit_hashmap(self, node):
		raise NotImplementedError

	def visit_collectionaccess(self, node):
		raise NotImplementedError

	def visit_print(self, node):  # TODO: Simplify this
		if isinstance(node.value, FuncCall):
			val = self.visit(node.value)
			if isinstance(val.type, ir.IntType):
				# noinspection PyUnresolvedReferences
				if val.type.width == 1:
					self.call('printb', [val])
					self.call('putchar', [ir.Constant(type_map[INT32](), 10)])
				else:
					self.call('printd', [val])
					self.call('putchar', [ir.Constant(type_map[INT32](), 10)])
		elif isinstance(node.value, Num) or self.search_scopes(node.value.value).type.pointee == type_map[INT]():
			self.call('printd', [self.visit(node.value)])
			self.call('putchar', [ir.Constant(type_map[INT32](), 10)])
		elif isinstance(self.search_scopes(node.value.value).type.pointee, ir.ArrayType):
			var = self.visit(node.value)
			var_ptr = self.builder.alloca(ir.ArrayType(var.type.element, var.type.count), name='var_ptr')
			self.builder.store(var, var_ptr)
			var_ptr_gep = self.builder.gep(var_ptr, [self.const(0), self.const(0)])
			var_ptr_gep = self.builder.bitcast(var_ptr_gep, ir.IntType(32).as_pointer())
			self.call('puts', [var_ptr_gep])
		elif isinstance(node.value, Var):
			val = self.visit(node.value)
			if isinstance(val.type, ir.IntType):
				# noinspection PyUnresolvedReferences
				if val.type.width == 1:
					self.call('printb', [val])
					self.call('putchar', [ir.Constant(type_map[INT32](), 10)])
			elif isinstance(val.type, ir.FloatType):
				raise NotImplementedError
			elif isinstance(val.type, ir.DoubleType):
				percent_f = self.stringz('%f')
				var_ptr = self.builder.alloca(ir.ArrayType(percent_f.type.element, percent_f.type.count), name='var_ptr')
				self.builder.store(percent_f, var_ptr)
				var_ptr_gep = self.builder.gep(var_ptr, [self.const(0), self.const(0)])
				var_ptr_gep = self.builder.bitcast(var_ptr_gep, ir.IntType(8).as_pointer())
				self.call('printf', [var_ptr_gep, self.visit(node.value)])
				self.call('putchar', [ir.Constant(type_map[INT32](), 10)])
		else:
			raise SyntaxError('Not known how to print {}'.format(self.visit(node.value)))

	def start_function(self, name, return_type, parameters, parameter_defaults=None, varargs=None):
		self.new_scope()
		ret_type = type_map[return_type.value]()
		args = [type_map[param.value]() for param in parameters.values()]
		arg_keys = [key for key in parameters.keys()]
		func_type = ir.FunctionType(ret_type, args)
		if parameter_defaults:
			func_type.parameter_defaults = parameter_defaults

		func_type.arg_order = arg_keys
		function = ir.Function(self.module, func_type, name)
		self.define(name, func_type, 1)
		self.function = function
		self.new_builder(self.add_block('entry'))
		self.exit_block = self.add_block('exit')

	def end_function(self, returned=False):
		if not returned:
			self.branch(self.exit_block)
		self.position_at_end(self.exit_block)
		if self.function.function_type.return_type != type_map[VOID]():
			retval = self.builder.load(self.search_scopes(RET_VAR))
			self.builder.ret(retval)
		else:
			self.builder.ret_void()
		self.builder = self.main_builder
		self.function = self.main_function

	def new_builder(self, block):
		self.builder = ir.IRBuilder(block)
		return self.builder

	def add_block(self, name):
		return self.function.append_basic_block(name)

	def position_at_start(self, block):
		self.builder.position_at_start(block)

	def position_at_end(self, block):
		self.builder.position_at_end(block)

	def cbranch(self, cond, true_block, false_block):
		self.builder.cbranch(cond, true_block, false_block)

	def branch(self, block):
		self.builder.branch(block)

	def switch(self, value, default):
		return self.builder.switch(value, default)

	def const(self, val, width=None):
		if isinstance(val, int):
			if width:
				return ir.Constant(ir.IntType(width), val)
			else:
				return ir.Constant(type_map[INT](), val)
		elif isinstance(val, float):
			return ir.Constant(type_map[DEC], val)
		elif isinstance(val, bool):
			return ir.Constant(type_map[INT](), int(val))
		elif isinstance(val, str):
			return self.stringz(val)
		else:
			raise NotImplementedError

	def allocate(self, val, name, typ):
		saved_block = self.builder.block
		var_addr = self.create_entry_block_alloca(name, typ)
		self.define(name, var_addr)
		self.builder.position_at_end(saved_block)
		self.builder.store(val, var_addr)

	def store(self, name, value):
		self.builder.store(value, self.search_scopes(name))

	def load(self, name):
		return self.builder.load(self.search_scopes(name))

	def call(self, name, args):
		return self.builder.call(self.module.get_global(name), args)

	def create_entry_block_alloca(self, name, typ):
		builder = ir.IRBuilder()
		builder.position_at_start(self.builder.function.entry_basic_block)
		return builder.alloca(typ, size=None, name=name)

	def _add_builtins(self):
		putchar_ty = ir.FunctionType(type_map[INT32](), [type_map[INT32]()])
		ir.Function(self.module, putchar_ty, 'putchar')

		printf_ty = ir.FunctionType(type_map[INT32](), [type_map[INT8]().as_pointer()], var_arg=True)
		ir.Function(self.module, printf_ty, 'printf')

		puts_ty = ir.FunctionType(type_map[INT32](), [type_map[INT32]().as_pointer()])
		ir.Function(self.module, puts_ty, 'puts')

		define_printd(ir, self.module)
		define_printb(ir, self.module)

	@staticmethod
	def stringz_type(string):
		return ir.ArrayType(type_map[INT8](), len(string) + 1)

	@staticmethod
	def stringz_pntr_type(string):
		return ir.ArrayType(type_map[INT8](), len(string) + 1).as_pointer()

	@staticmethod
	def stringz(string):
		n = len(string) + 1
		buf = bytearray((' ' * n).encode('ascii'))
		buf[-1] = 0
		buf[:-1] = string.encode('utf-8')
		return ir.Constant(ir.ArrayType(type_map[INT8](), n), buf)

	@staticmethod
	def stringz_pntr(string):
		n = len(string) + 1
		buf = bytearray((' ' * n).encode('ascii'))
		buf[-1] = 0
		buf[:-1] = string.encode('utf-8')
		return ir.Constant(ir.ArrayType(type_map[INT8](), n).as_pointer(), buf)

	def generate_code(self, node):
		return self.visit(node)

	def evaluate(self, optimize=True, llvmdump=False):
		if llvmdump:
			print('======== Unoptimized LLVM IR')
			print(str(self.module))
		llvmmod = llvm.parse_assembly(str(self.module))
		if optimize:
			pmb = llvm.create_pass_manager_builder()
			pmb.opt_level = 2
			pm = llvm.create_module_pass_manager()
			pmb.populate(pm)
			pm.run(llvmmod)
			if llvmdump:
				print('======== Optimized LLVM IR')
				print(str(llvmmod))
		target_machine = self.target.create_target_machine()
		with llvm.create_mcjit_compiler(llvmmod, target_machine) as ee:
			ee.finalize_object()
			fptr = CFUNCTYPE(c_void_p)(ee.get_function_address('__main__'))
			fptr()

if __name__ == '__main__':
	from my_lexer import Lexer
	from my_parser import Parser
	from my_symbol_table_builder import SymbolTableBuilder
	file = 'math.my'
	code = open(file).read()
	lexer = Lexer(code, file)
	parser = Parser(lexer)
	t = parser.parse()
	symtab_builder = SymbolTableBuilder(parser.file_name)
	symtab_builder.build(t)
	if not symtab_builder.warnings:
		generator = CodeGenerator(parser.file_name)
		generator.generate_code(t)
		# generator.evaluate(True, True)
		# generator.evaluate(False, True)
		generator.evaluate(True, False)
		# generator.evaluate(False, False)
	else:
		print('Did not run')
