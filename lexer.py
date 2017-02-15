from tokens import Token

ALPHANUMERIC = 'alphanumeric'
NUMERIC = 'numeric'
OPERATIC = 'operatic'
WHITESPACE = 'whitespace'
COMMENT = 'comment'
ESCAPE = 'escape'
OPERATORS = (
	'(', ')', '[', ']', '{', '}', ',', ':', '.', '&', '|', '@',	'^', '~', '+', '-', '*', '/', '<', '>', '%',
	'=', '//', '**', '<=', '>=', '==', '!=', '+=', '-=', '*=', '/=', '//=', '%=', '**=', '<<', '>>', 'is not',
	'not in', 'is', 'in', 'not', 'and', 'or'
)


class Lexer(object):
	def __init__(self, text):
		self.text = text
		self.pos = 0
		self.current_char = self.text[self.pos]
		self.char_type = None
		self.word = ''
		self.word_type = None
		self.line_num = 1

	def next(self):
		self.pos += 1
		if self.pos > len(self.text) - 1:
			self.current_char = None
			self.char_type = None
		else:
			self.current_char = self.text[self.pos]
			self.char_type = self.get_type(self.current_char)

	def reset_word(self):
		old_word = self.word
		self.word = ''
		self.word_type = None
		return old_word

	def peek(self, num):
		peek_pos = self.pos + num
		if peek_pos > len(self.text) - 1:
			return None
		else:
			return self.text[peek_pos]

	def skip_whitespace(self):
		while self.current_char is not None and self.current_char.isspace():
			self.next()

	@staticmethod
	def get_type(char):
		if char.isspace():
			return WHITESPACE
		if char == '#':
			return COMMENT
		if char == '\\':
			return ESCAPE
		if char in OPERATORS:
			return OPERATIC
		try:
			int(char)
			return NUMERIC
		except ValueError:
			return ALPHANUMERIC

	def get_next_token(self):
		if self.current_char is None:
			return Token('END', '', self.line_num)

		if self.current_char == '#':
			while self.current_char != '\n':
				self.next()

		if self.current_char == '\n':
			self.reset_word()
			self.line_num += 1
			self.next()
			return Token('NEWLINE', '\\n', self.line_num - 1)
		elif self.current_char == '\t':
			self.reset_word()
			self.next()
			return Token('INDENT', '\\t', self.line_num)

		if self.current_char.isspace():
			self.skip_whitespace()

		if self.current_char == '#':
			while self.current_char != '\n':
				self.next()
			self.reset_word()
			self.line_num += 1
			self.next()
			return Token('NEWLINE', '\\n', self.line_num - 1)

		if self.current_char == '"':
			self.next()
			while self.current_char != '"':
				if self.current_char == '\\' and self.peek(1) == '"':
					self.next()
				self.word += self.current_char
				self.next()
			self.next()
			return Token('STRING', self.reset_word(), self.line_num)
		elif self.current_char == "'":
			self.next()
			while self.current_char != "'":
				if self.current_char == '\\' and self.peek(1) == "'":
					self.next()
				self.word += self.current_char
				self.next()
			self.next()
			return Token('STRING', self.reset_word(), self.line_num)

		if not self.char_type:
			self.char_type = self.get_type(self.current_char)
		if not self.word_type:
			self.word_type = self.char_type

		if self.word_type == ALPHANUMERIC:
			while self.char_type == ALPHANUMERIC or self.char_type == NUMERIC:
				self.word += self.current_char
				self.next()
			return Token('NAME', self.reset_word(), self.line_num)

		if self.word_type == NUMERIC:
			while self.char_type == NUMERIC or self.current_char == '.':
				self.word += self.current_char
				self.next()
				if self.char_type == ALPHANUMERIC:
					raise SyntaxError('Variables cannot start with numbers')
			return Token('NUMBER', self.reset_word(), self.line_num)

		if self.word_type == OPERATIC:
			while self.char_type == OPERATIC:
				self.word += self.current_char
				self.next()
			return Token('OP', self.reset_word(), self.line_num)

		if self.char_type == ESCAPE:
			self.reset_word()
			self.next()
			line_num = self.line_num
			if self.current_char == '\n':
				self.line_num += 1
			self.next()
			return Token(ESCAPE, '\\', line_num)

		raise SyntaxError('Unknown character')

	def analyze(self):
		token = self.get_next_token()
		while token.type != 'END':
			yield token
			token = self.get_next_token()
		yield token


if __name__ == '__main__':
	lexer = Lexer(open('example.my').read())
	for t in lexer.analyze():
		if t.type != 'NEWLINE':
			print(t, end=' ')
		else:
			print(t)