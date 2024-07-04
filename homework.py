import http
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


class GeneralError(Exception):
    """Общая ошибка."""

    pass


class CriticalError(Exception):
    """Критическая ошибка."""

    pass


logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID
    }
    if not all(tokens.values()):
        missing_tokens = [name for name, token in tokens.items() if
                          not token]
        raise CriticalError(f'Отсутствуют токены: {missing_tokens}')


def send_message(bot, message):
    """Отправляет сообщение со статусом работы в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение отправлено!')
    except Exception as e:
        raise GeneralError(f'Сообщение {str(e)} не отправлено!')


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ при успешном запросе."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if response.status_code != http.HTTPStatus.OK:
            raise GeneralError('Отсутствует доступ к эндпоинту')
        check_response(response.json())

    except requests.RequestException as req_err:
        return f'Возникла проблема: {req_err}'
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
    timestamp, last_message, last_error_message = 0, '', ''
    try:
        check_tokens()
        while True:
            try:
                response = get_api_answer(timestamp)
                homework = response.get('homeworks')
                timestamp = response.get('current_date')
                if homework:
                    message = parse_status(homework[0])
                    if last_message != message:
                        send_message(bot, message)
                        last_message = message
                else:
                    # Пытался так же как с error и critical выбрасывать
                    # кастомное исключение DebugError, но на такой
                    # метод ругался тест.
                    logging.debug('Список домашних работ пуст')
            except GeneralError as error:
                logging.error(error)
            except Exception as error:
                error_message = f'Сбой в работе программы: {error}'
                if last_error_message != error_message:
                    logging.error(error_message)
                    send_message(bot, error_message)
                    last_error_message = error_message
            finally:
                time.sleep(RETRY_PERIOD)
    except CriticalError as error:
        logging.critical(error)
        exit(1)


if __name__ == '__main__':
    main()
