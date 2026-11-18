import datetime
import logging

import lunchbot


def main() -> None:
    day = datetime.datetime.today().weekday()

    if day in [0, 2, 4]:
        lunchbot._set_vote_enable(False)
        lunchbot._post_to_hipchat("Rogue One", "It has been decided! Go forth and lunch..", "green")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
