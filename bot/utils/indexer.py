from dotenv import load_dotenv

from bot.setup import build_vectorstore


def main():
    load_dotenv()
    build_vectorstore()


if __name__ == "__main__":
    main()
