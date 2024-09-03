import logging
import pika
from datetime import datetime


# decorator for updating log file name
def update_handler(logger: logging) -> callable:
    def decorator(func: callable) -> callable:
        def wrapper(*args, **kwargs) -> None:
            logger.FileHandler = f"logger/{datetime.now().date()}.log"

            return func(*args, **kwargs)

        return wrapper

    return decorator


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        filename=f"logger/{datetime.now().date()}.log",
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))

    channel = connection.channel()

    channel.queue_declare("logging.database")
    channel.queue_declare("logging.workers")

    logging.info("Logger started successfully")

    @update_handler(logger=logging)
    def database_callback(ch, method, properties, body) -> None:
        # list of levels and their logging methods
        levels = {
            "INFO:": logging.info,
            "WARNING:": logging.warning,
            "ERROR:": logging.error,
            "CRITICAL:": logging.critical,
        }

        # decode message and determine level
        message = body.decode("utf-8")
        level = message.split(" ")[0]

        # write logs based on level if valid
        if level not in levels:
            logging.error("Invalid logs from database: " + message)
        else:
            levels[level]("DATABASE: " + " ".join(message.split(" ")[1:]))

        # finally, acknowledge receiving the message
        ch.basic_ack(delivery_tag=method.delivery_tag)

    @update_handler(logger=logging)
    def workers_callback(ch, method, properties, body) -> None:

        # list of levels and their logging methods
        levels = {
            "INFO:": logging.info,
            "WARNING:": logging.warning,
            "ERROR:": logging.error,
            "CRITICAL:": logging.critical,
        }

        # decode message and determine level
        message = body.decode("utf-8")
        level = message.split(" ")[0]

        # write logs based on level if valid
        if level not in levels:
            logging.error("Invalid logs from workers: " + message)
        else:
            levels[level]("WORKERS: " + " ".join(message.split(" ")[1:]))

        # finally, acknowledge receiving the message
        ch.basic_ack(delivery_tag=method.delivery_tag)

    # setup consumer queues
    channel.basic_consume("logging.database", on_message_callback=database_callback)
    channel.basic_consume("logging.workers", on_message_callback=workers_callback)

    channel.start_consuming()


if __name__ == "__main__":
    main()
