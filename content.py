import random
import string

WORD_SETS = {
    'ru': {
        'daily': 'мы вы он ты дом кот чай хлеб суп сок сыр окно стол стул чашка ложка кухня сахар молоко тарелка завтрак комната магазин продукты телефон одежда посуда'.split(),
        'study': 'ум код год час курс план тест урок лист стол труд счёт книга школа ответ задача лекция тетрадь студент предмет пример формула решение практика программа'.split(),
        'nature': 'лес мир сон сад мяч день ночь утро река море гора поле снег дождь ветер трава цветок солнце облако берёза осень зима озеро воздух тропинка деревья рассвет природа'.split()
    },
    'en': {
        'daily': 'we he it us cat dog tea cup red blue home book food soup milk door room desk chair bread water kitchen dinner window market clothes breakfast'.split(),
        'study': 'code time task test note plan page word file line read work learn school lesson answer number student teacher subject notebook program practice question'.split(),
        'nature': 'sun sky day tree bird moon star rain wind road snow lake leaf hill rock river forest garden flower summer winter meadow mountain weather sunshine'.split()
    }
}

SENTENCE_SETS = {
    'ru': {
        'daily': [
            'Я поставил чайник и открыл окно.',
            'Кот уснул на стуле рядом со столом.',
            'По дороге домой мы зашли в магазин.',
            'На завтрак были каша и горячий чай.',
            'Автобус приехал на пять минут позже.',
            'Вечером я приготовлю ужин и посмотрю фильм.'
        ],
        'study': [
            'После пары мы пошли в библиотеку.',
            'Я записал решение задачи в тетрадь.',
            'До зачёта осталось повторить две темы.',
            'Программа считает сумму чисел в списке.',
            'Мы нашли ошибку и запустили код ещё раз.',
            'На следующей неделе нужно сдать проект.'
        ],
        'nature': [
            'Утром над рекой поднялся лёгкий туман.',
            'За окном идёт дождь и шумят деревья.',
            'Мы остановились у озера и сделали привал.',
            'В парке появились первые жёлтые листья.',
            'Солнце скрылось за облаками перед закатом.',
            'По узкой тропинке можно дойти до берега.'
        ]
    },
    'en': {
        'daily': [
            'I made some tea and opened the window.',
            'The cat is sleeping on my favourite chair.',
            'We stopped at the shop on our way home.',
            'There is fresh bread on the kitchen table.',
            'The bus arrived five minutes late today.',
            'I will cook dinner and watch a film tonight.'
        ],
        'study': [
            'We went to the library after class.',
            'I wrote the answer in my notebook.',
            'There are two more topics to revise.',
            'This program adds the numbers in a list.',
            'We fixed the error and ran the code again.',
            'Our project is due at the end of next week.'
        ],
        'nature': [
            'A light mist covered the river this morning.',
            'The rain is falling on the trees outside.',
            'We stopped by the lake for a short break.',
            'The first yellow leaves appeared in the park.',
            'The sun went behind the clouds before sunset.',
            'A narrow path leads down to the river bank.'
        ]
    }
}

CODE_SETS = {
    'python': {
        'basics': [
            'name = "Alex"\nprint("Hello, " + name)',
            'price = 120\ncount = 3\nprint(price * count)',
            'numbers = [2, 4, 6]\nprint(sum(numbers))'
        ],
        'loops': [
            'total = 0\nfor number in range(5):\n    total += number\nprint(total)',
            'words = ["cat", "dog", "sun"]\nfor word in words:\n    print(word.upper())',
            'count = 3\nwhile count > 0:\n    print(count)\n    count -= 1'
        ],
        'functions': [
            'def greet(name):\n    return "Hello, " + name\n\nprint(greet("World"))',
            'def square(number):\n    return number * number\n\nprint(square(4))',
            'def is_even(number):\n    return number % 2 == 0\n\nprint(is_even(8))'
        ]
    },
    'javascript': {
        'basics': [
            'const name = "Alex";\nconsole.log("Hello, " + name);',
            'const price = 120;\nconst count = 3;\nconsole.log(price * count);',
            'const colors = ["red", "blue"];\nconsole.log(colors.length);'
        ],
        'loops': [
            'let total = 0;\nfor (let i = 0; i < 5; i++) {\n    total += i;\n}',
            'const words = ["cat", "dog"];\nfor (const word of words) {\n    console.log(word);\n}',
            'let count = 3;\nwhile (count > 0) {\n    console.log(count);\n    count--;\n}'
        ],
        'functions': [
            'function greet(name) {\n    return "Hello, " + name;\n}',
            'function square(number) {\n    return number * number;\n}',
            'function isEven(number) {\n    return number % 2 === 0;\n}'
        ]
    },
    'html': {
        'basics': [
            '<h1>My page</h1>\n<p>Hello, world!</p>',
            '<a href="/about">About us</a>\n<button>Open</button>',
            '<img src="photo.jpg" alt="A green tree">'
        ],
        'markup': [
            '<ul>\n    <li>Tea</li>\n    <li>Coffee</li>\n</ul>',
            '<main>\n    <h1>News</h1>\n    <p>A new post.</p>\n</main>',
            '<form>\n    <input type="text">\n    <button>Send</button>\n</form>'
        ],
        'styles': [
            'body {\n    color: #222;\n    margin: 0;\n    padding: 20px;\n}',
            'button {\n    background: white;\n    border: 1px solid gray;\n}',
            '.card {\n    width: 300px;\n    padding: 16px;\n    margin: auto;\n}'
        ]
    }
}

WORDS = {language: [word for words in groups.values() for word in words] for language, groups in WORD_SETS.items()}
SENTENCES = {language: [text for texts in groups.values() for text in texts] for language, groups in SENTENCE_SETS.items()}
CODE = {language: [text for texts in groups.values() for text in texts] for language, groups in CODE_SETS.items()}
MODES = {'words': 'Слова', 'sentences': 'Предложения', 'code': 'Код', 'symbols': 'Символы'}
LEVELS = {'words': 1, 'sentences': 1, 'code': 2, 'symbols': 3}
VARIANTS = {
    'words': ('mixed', 'daily', 'study', 'nature'),
    'sentences': ('mixed', 'daily', 'study', 'nature'),
    'code': ('mixed', 'basics', 'loops', 'functions', 'markup', 'styles'),
    'symbols': ('mixed', 'letters', 'numbers', 'punctuation')
}
ACHIEVEMENTS = [
    {'id': 'first', 'name': 'Первый шаг', 'description': 'Завершить первую тренировку', 'icon': '01'},
    {'id': 'fast', 'name': 'Быстрые руки', 'description': 'Достичь 200 символов в минуту', 'icon': '02'},
    {'id': 'perfect', 'name': 'Точно в цель', 'description': 'Пройти упражнение без ошибок', 'icon': '03'},
    {'id': 'steel', 'name': 'Стальной палец', 'description': '1000 правильных нажатий подряд', 'icon': '04'},
    {'id': 'genius', 'name': 'Печатный гений', 'description': 'Достичь 300 слов в минуту', 'icon': '05'},
    {'id': 'regular', 'name': 'Вошло в привычку', 'description': 'Завершить 10 тренировок', 'icon': '06'}
]


def make_text(mode, language, difficulty, code_language, variant='mixed', previous=''):
    count = {'easy': 12, 'medium': 22, 'hard': 35}[difficulty]
    if mode == 'words':
        words = WORDS[language] if variant == 'mixed' else WORD_SETS[language][variant]
        words = [word for word in words if 2 <= len(word) <= 10]
        if difficulty == 'easy':
            words = [word for word in words if len(word) <= 4]
        elif difficulty == 'hard':
            words = [word for word in words if len(word) >= 5]
        result = []
        for _ in range(count):
            options = [word for word in words if not result or word != result[-1]]
            result.append(random.choice(options))
        return ' '.join(result)
    if mode in ('sentences', 'code'):
        if mode == 'sentences':
            texts = SENTENCES[language] if variant == 'mixed' else SENTENCE_SETS[language][variant]
            separator = ' '
        else:
            texts = CODE[code_language] if variant == 'mixed' else CODE_SETS[code_language][variant]
            separator = '\n\n'
        amount = {'easy': 1, 'medium': 2, 'hard': 3}[difficulty]
        options = [text for text in texts if amount > 1 or text != previous]
        selected = random.sample(options, amount)
        result = separator.join(selected)
        if result == previous:
            selected.reverse()
        return separator.join(selected)
    letters = string.ascii_lowercase if language == 'en' else 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
    punctuation = '!@#$%^&*()-_=+[]{};:,.?/' if language == 'en' else '!"№;%:?*()-_=+.,/'
    alphabets = {'mixed': letters + string.digits + punctuation, 'letters': letters,
                 'numbers': string.digits, 'punctuation': letters + punctuation}
    length = {'easy': 3, 'medium': 5, 'hard': 8}[difficulty]
    return ' '.join(''.join(random.choices(alphabets[variant], k=length)) for _ in range(count))
