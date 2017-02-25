import warnings
from my_visitor import NodeVisitor
from my_symbol_table import VarSymbol
from my_symbol_table import CollectionSymbol
from my_symbol_table import FuncSymbol
from my_symbol_table import SymbolTable
from my_ast import VarDecl, HashMap
from my_ast import Collection
from my_grammar import *

def flatten(container):
	for i in container:
		if isinstance(i, (list,tuple)):
			for j in flatten(i):
				if j:
					yield j
		else:
			if i:
				yield i

def warning_on_one_line(message, category, filename, lineno, file=None, line=None):
	return 'Warning: {}\n'.format(message)

warnings.formatwarning = warning_on_one_line


class SymbolTableBuilder(NodeVisitor):
	def __init__(self):
		self.symtab = SymbolTable()

	def build(self, node):
		res = self.visit(node)
		if self.symtab.unvisited_symbols:
			warnings.warn('Unused variables ({})'.format(','.join(sym_name for sym_name in self.symtab.unvisited_symbols)))
		return res

	def visit_program(self, node):
		return self.visit(node.block)

	def visit_block(self, node):
		declaraions = []
		for declaration in node.declarations:
			declaraions.append(self.visit(declaration))
		declaraions.append(self.visit(node.compound_statement))
		return declaraions

	def visit_controlstructure(self, node):
		blocks = []
		for x, block in enumerate(node.blocks):
			self.visit(node.comps[x])
			blocks.append(self.visit(block))
		return blocks

	def visit_constant(self, node):
		if node.value == TRUE or node.value == FALSE:
			return self.symtab.lookup(BOOL)
		elif node.value == NAN or node.value == INF or node.value == NEGATIVE_INF:
			return self.symtab.lookup(DEC)
		else:
			return NotImplementedError

	def visit_num(self, node):
		return self.symtab.infer_type(node.value)

	def visit_str(self, node):
		return self.symtab.infer_type(node.value)

	@staticmethod
	def visit_type(node):
		return node.value

	def visit_assign(self, node): #TODO clean up this mess of a function
		collection_type = None
		if isinstance(node.left, VarDecl):
			var_name = node.left.var_node.value
			value = self.symtab.infer_type(node.left.type_node)
		elif isinstance(node.right, Collection):
			var_name = node.left.value
			value, collection_type = self.visit(node.right)
		else:
			var_name = node.left.value
			value = self.visit(node.right)
		lookup_var = self.symtab.lookup(var_name)
		if not lookup_var:
			if collection_type:
				col_sym = CollectionSymbol(var_name, value, collection_type)
				col_sym.val_assigned = True
				self.symtab.define(col_sym)
			else:
				var_sym = VarSymbol(var_name, value)
				var_sym.val_assigned = True
				self.symtab.define(var_sym)
		else:
			self.symtab.search_scopes(var_name).val_assigned = True
			if lookup_var.type in (self.symtab.lookup(DEC), self.symtab.lookup(FLOAT)):
				if value in (self.symtab.lookup(INT), self.symtab.lookup(DEC), self.symtab.lookup(FLOAT)):
					return
			if (value.type and lookup_var.type is not value.type) or lookup_var.type is not value:
				raise TypeError

	def visit_opassign(self, node):
		left = self.visit(node.left)
		right = self.visit(node.right)
		left_type = self.symtab.infer_type(left)
		right_type = self.symtab.infer_type(right)
		any_type = self.symtab.lookup(ANY)
		if left_type in (self.symtab.lookup(DEC), self.symtab.lookup(FLOAT)): #TODO: implicit type conversion needs an expanded official solution
			if right_type in (self.symtab.lookup(INT), self.symtab.lookup(DEC), self.symtab.lookup(FLOAT)):
				return left_type
		if right_type is left_type or left_type is any_type or right_type is any_type:
			return left_type
		else:
			raise TypeError

	def visit_var(self, node):
		var_name = node.value
		val = self.symtab.lookup(var_name)
		if val is None:
			raise NameError(repr(var_name))
		else:
			if not val.val_assigned:
				raise SyntaxError('{} is being accessed while not yet defined'.format(var_name))
			val.accessed = True
			return val

	def visit_binop(self, node):
		if node.op.value == CAST:
			self.symtab.lookup(node.left.value).accessed = True
			return self.symtab.infer_type(node.right)
		else:
			left = self.visit(node.left)
			right = self.visit(node.right)
			left_type = self.symtab.infer_type(left)
			right_type = self.symtab.infer_type(right)
			any_type = self.symtab.lookup(ANY)
			if left_type in (self.symtab.lookup(INT), self.symtab.lookup(DEC), self.symtab.lookup(FLOAT)):
				if right_type in (self.symtab.lookup(INT), self.symtab.lookup(DEC), self.symtab.lookup(FLOAT)):
					return left_type
			if right_type is left_type or left_type is any_type or right_type is any_type:
				return left_type
			else:
				raise TypeError

	def visit_unaryop(self, node):
		return self.visit(node.expr)

	def visit_compound(self, node):
		results = []
		for child in node.children:
			results.append(self.visit(child))
		return results

	def visit_funcdecl(self, node):
		func_name = node.name.value
		return_type = node.return_type.value
		func_type = self.symtab.lookup(return_type)
		self.symtab.new_scope()
		for k, v in node.parameters.items():
			var_sym = VarSymbol(k, self.symtab.lookup(v.value))
			var_sym.val_assigned = True
			self.symtab.define(var_sym)
		func_symbol = FuncSymbol(func_name, func_type, node.parameters, node.body)
		self.symtab.define(func_symbol, 1)
		return_var_type = self.visit(func_symbol.body)
		return_var_type = list(flatten(return_var_type))
		for ret_type in return_var_type:
			if ret_type is not func_type:
				raise TypeError('The actual return type does not match the declared return type')
		self.symtab.drop_top_scope()

	def visit_funccall(self, node):
		func_name = node.name.value
		func = self.symtab.search_scopes(func_name)
		for arg in node.arguments:
			self.visit(arg)
		if func is None:
			raise NameError(repr(func_name))
		else:
			func.accessed = True
			return func.type

	def visit_return(self, node):
		res = self.visit(node.value)
		return res

	def visit_noop(self, node):
		pass

	def visit_vardecl(self, node):
		type_name = node.type_node.value
		type_symbol = self.symtab.lookup(type_name)
		var_name = node.var_node.value
		var_symbol = VarSymbol(var_name, type_symbol)
		self.symtab.define(var_symbol)

	def visit_collection(self, node):
		types = []
		for item in node.items:
			types.append(self.visit(item))
		if types[1:] == types[:-1]:
			return self.symtab.lookup(ARRAY), types[0]
		else:
			return self.symtab.lookup(LIST), self.symtab.lookup(ANY)

	def visit_hashmap(self, node):
		for key in node.items.keys():
			value = self.symtab.search_scopes(key)
			if value:
				value.accessed = True
		return self.symtab.lookup(DICT)

if __name__ == '__main__':
	from my_lexer import Lexer
	from my_parser import Parser
	code = open('math.my').read()
	lexer = Lexer(code)
	parser = Parser(lexer)
	t = parser.parse()
	symtab_builder = SymbolTableBuilder()
	symtab = symtab_builder.build(t)
	print(symtab)