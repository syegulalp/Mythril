int greets
hello = 23
hi2=hello+1.2
hmm = "what is\" going' on"
str where
things[int] = [1, 2, 3]
stuff[str, str] = {'first_name': 'samus', 'last_name': 'aran'}

if where is not hello \
	and true
	print('They not the same')

if hello == 23
	print('whosits') # line comment
else
	print('whatsits')

if 2 in things
	print('yes')

if 2 not in things
	print('no')

def void scoots(func sploots)
	whats = 'loves'
	print('snoots')
	sploots(whats)

def int fib(int num)
	if num = 0
		return 0
	else if num = 1
		return 1
	else
		return fib(n - 1) + fib(n - 2)

scoots(
	void func(str verb)
		print('Snape')
		print(verb)
		print('Dumbledore')
	)

enum genders(
	MALE,
	FEMALE,
	OTHER
)

abst class Person
	str species = 'Human'

	def Person(str name, int age, enum gender, str haircolor)
		this.age = age
		this.gender # Automtically assigns gender from parameter
		this.haircolor = haircolor
		str this.fav_color

vulgar_words[str] = ['Trump', 'Pence']

class Boy(Person)
	def Boy(str, name, int age, haircolor)
		require age < 18
		super.Person(name=name, age=age, gender=gender.MALE, haircolor=haircolor)

	def void talk(str words)
		assert word not in vulgar_words for word in words.split(' ')
		print(words)

	def void say_age()
		print('I am {} years old'.format(this.age))

	get time_till_adult
		return 18 - this.age

	set dye_hair(str color)
		this.haircolor = color

	prop favorite_color
		get
			return this.fav_color
		set(str color)
			this.fav_color = color