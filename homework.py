import http
import logging
from logging.handlers import RotatingFileHandler
import os
import time

import requests
from telebot import TeleBot
from dotenv import load_dotenv

from exceptions import CriticalError

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

logger = logging.getLogger(__name__)
terminal_handler = logging.StreamHandler()
file_handler = RotatingFileHandler(
    'main.log', maxBytes=5 * 1024 * 1024, backupCount=5
)
formater = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(name)s, '
    'строка: %(lineno)d, функция: %(funcName)s, %(message)s'
)

logger.setLevel(logging.DEBUG)
terminal_handler.setFormatter(formater)
file_handler.setFormatter(formater)
logger.addHandler(terminal_handler)
logger.addHandler(file_handler)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    valid = True
    tokens = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID
    }
    if not all(tokens.values()):
        missing_tokens = [name for name, token in tokens.items() if
                          not token]
        valid = False
        return valid, missing_tokens
    return valid, None


def send_message(bot, message):
    """Отправляет сообщение со статусом работы в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено!')
    except requests.RequestException:
        raise Exception(
            f'Сообщение не отправлено!'
        )


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ при успешном запросе."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        check_response(response.json())
    except requests.RequestException as req_err:
        raise Exception(f'Возникла проблема: {req_err}')
    if response.status_code != http.HTTPStatus.OK:
        raise Exception('Отсутствует доступ к эндпоинту')
    return response.json()


def check_response(response):
    """Проверяет правильно полученный API ответ."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Тип переменной "response": ожидался dict, '
            f'получен {type(response)}'
        )
    if 'homeworks' not in response:
        raise KeyError(
            'Отсутствует ключ "homeworks" в полученном ответе'
        )

    if not isinstance(response['homeworks'], list):
        raise TypeError(
            f'Тип переменной "homeworks": ожидался list, '
            f'получен {type(response["homeworks"])}')


def parse_status(homework):
    """Извлекает из информации статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError(
            'homework_name отсутствует в списке '
            'домашних работ "homework"'
        )
    if homework['status'] == 'unknown':
        raise KeyError('Статус работы "unknown"')
    homework_name = homework['homework_name']
    status = homework['status']
    if status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[status]
    else:
        verdict = 'Статус не определен.'
    return (
        f'Изменился статус проверки работы '
        f'"{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp, last_message, last_error_message = 0, '', ''
    try:
        valid, missing_tokens = check_tokens()
        if not valid:
            raise CriticalError(f'Отсутствуют токены: {missing_tokens}')
        while True:
            try:
                response = get_api_answer(timestamp)
                homework = response.get('homeworks')
                timestamp = response.get('current_date')

                message = parse_status(homework[0])
                if last_message != message:
                    send_message(bot, message)
                    last_message = message
                if not homework:
                    logger.debug('Список домашних работ пуст')
            except Exception as error:
                error_message = f'Сбой в работе программы: {error}'
                logger.error(error_message)
                if last_error_message != error_message:
                    send_message(bot, error_message)
                    last_error_message = error_message
            finally:
                time.sleep(RETRY_PERIOD)
    except CriticalError as error:
        logger.critical(error)
        exit(1)


if __name__ == '__main__':
    main()
