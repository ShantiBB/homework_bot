import logging
import os
import time

import requests
from telebot import TeleBot
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    logging.critical(
        'Отсутствуют данные в пространстве переменных'
    )
    return False


def send_message(bot, message):
    """Отправляет сообщение со статусом работы в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение отправлено!')
    except Exception:
        logging.error('Сообщение не отправлено!')


def get_api_answer(timestamp):
    """
    Делает запрос к API и возвращает ответ при успешном запросе,
    иначе выбрасывает исключение.
    """
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        check_response(response.json())

    except requests.RequestException:
        return 'API error'
    if response.status_code != 200:
        logging.error('Отсутствует доступ к эндпоинту')
        raise requests.RequestException
    return response.json()


def check_response(response):
    """Проверяет правильно полученный API ответ."""
    if (
        not isinstance(response, dict)
        or not isinstance(response.get('homeworks'), list)
    ):
        raise TypeError
    if not response.get('homeworks'):
        logging.debug('Список домашних работ пуст')


def parse_status(homework):
    """
    Извлекает из информации статус домашней работы и выводит статус
    данной работы.
    """
    if (
            not homework.get('homework_name')
            or homework.get('status') == 'unknown'
    ):
        raise KeyError
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    verdict = HOMEWORK_VERDICTS[status]

    return (
        f'Изменился статус проверки работы '
        f'"{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = time.time() - RETRY_PERIOD

    while True:
        try:
            if not check_tokens():
                break
            homework = get_api_answer(timestamp).get('homeworks')
            if homework:
                send_message(bot, parse_status(homework[0]))

        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
