# -*- coding:utf-8 -*-

from weekly_report import main as weekly_report_main


def main(event, context):
    weekly_report_main.start()


if __name__ == '__main__':
    main(None, None)
