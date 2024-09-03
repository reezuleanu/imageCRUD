import pika

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))

channel = connection.channel()


# queue for database logs
channel.queue_declare("logging.database")

# queue for worker logs
channel.queue_declare("logging.workers")


def rabbit_logging(queue: str, message: str) -> None:
    """Send message to logger via RabbitMQ

    Args:
        queue (str): name of queue
        message (str): message
    """

    channel.basic_publish("", queue, message)
