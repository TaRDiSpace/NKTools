# -*- coding:utf-8 -*-

import datetime
import json
import logging
import os
import re
import smtplib
import sys
import time

import requests

BASE_DIR = sys.path[0]
sys.path.append(os.path.join(BASE_DIR, ".."))

from utils import holidays, sendmail

LOG_FILE = os.path.join(BASE_DIR, 'weekly_report.log')


def initLog():
    logging.getLogger().setLevel(logging.INFO)
    _logger = logging.getLogger('Weekly')
    # 控制台日志(debug环境才输出)
    if 'NK_DEBUG' in os.environ:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(
            logging.Formatter(
                '[%(asctime)s] ::%(name)s::%(levelname)s:: %(message)s'))
        _logger.addHandler(console)
    # 文件日志
    filehandler = logging.FileHandler(LOG_FILE, 'a', encoding='utf-8')
    filehandler.setLevel(logging.INFO)
    filehandler.setFormatter(
        logging.Formatter(
            '[%(asctime)s] ::%(name)s::%(levelname)s:: %(message)s'))
    _logger.addHandler(filehandler)
    return _logger


logger = initLog()


class WorkDate:
    def __init__(self):
        self.today = datetime.date.today()
        self.weekday = self.today.weekday()
        self.firstday = self.today - datetime.timedelta(days=self.weekday)

    def get_work_time(self):
        '''
        获取当周工作日
        '''
        holiday_json = holidays.get_holiday_json()
        weekdate = []
        for i in range(0, 7):
            now_date = self.firstday + datetime.timedelta(days=i)
            now_date_str = now_date.strftime('%Y-%m-%d')
            if now_date_str in holiday_json['relax']:
                continue
            elif now_date_str in holiday_json['work']:
                weekdate.append(now_date_str)
            elif now_date.weekday() in [5, 6]:
                continue
            else:
                weekdate.append(now_date_str)
        weekhours = '@eq@8@end@'.join(weekdate) + '@eq@8'
        weekdate = ','.join(weekdate)
        logger.info('当周工作日期: ' + weekdate)
        logger.info('当周工作时间: ' + weekhours)
        return weekdate, weekhours


class WeeklyReport:
    login_url = 'http://bpowls.northking.net:7070/pm/userLogin!login.do'
    logout_url = 'http://bpowls.northking.net:7070/pm/userLogin!loginOut.do'
    query_url = 'http://bpowls.northking.net:7070/pm/proLogInput!queryByLogDate.do'
    save_url = 'http://bpowls.northking.net:7070/pm/proLogInput!saveLog.do'
    submit_url = 'http://bpowls.northking.net:7070/pm/proLogInput!submitLog.do'
    headers = {
        'Host': 'bpowls.northking.net:7070',
        'Origin': 'http://bpowls.northking.net:7070',
        'X-Requested-With': 'ajax-request',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.8',
    }

    def __init__(self):
        self.session = requests.Session()
        self.usr = None
        self.pwd = None
        self.staffId = None
        self.projectCode = None
        self.content = None
        self.is_submit = False
        self.today = datetime.date.today()
        wd = WorkDate()
        self.weekdate, self.weekhours = wd.get_work_time()

    def load_config(self):
        '''
        加载环境变量配置
        '''
        self.usr = os.environ['OA_USERNAME']
        self.pwd = os.environ['OA_PASSWORD']
        self.is_submit = os.environ['OA_IS_SUBMIT']
        if not self.usr or not self.pwd:
            raise Exception('未读取到用户配置')

    def login(self, usr=None, pwd=None):
        '''
        登录
        '''
        if usr is None:
            usr = self.usr
        if pwd is None:
            pwd = self.pwd
        params = {'code': usr, 'password': pwd}
        self.headers['Referer'] = 'http://bpowls.northking.net:7070/pm/'
        response = self.session.post(
            self.login_url, data=params, headers=self.headers, timeout=3)
        res = json.loads(response.text)
        if 'errorMessage' in res:
            raise Exception('登录失败: ' + res['errorMessage'])
        else:
            info = res['pojoMap']
            logger.info('登录成功: [%s][%s][%s]', info['smOrganByOrgId.name'],
                        info['name'], info['id'])
            self.staffId = info['id']
            if not self.staffId:
                raise('登录失败: 未获取到员工编号')

    def logout(self):
        '''
        注销
        '''
        self.session.post(self.logout_url)

    def query_log(self, query_date=None):
        '''
        查询周报
        '''
        if query_date is None:
            query_date = self.today
        self.headers['Referer'] = 'http://bpowls.northking.net:7070/pm/pages/proLog/logInput.html'
        params = {"staffId": self.staffId, "logRecordDate": query_date}
        response = self.session.post(
            self.query_url, data=params, headers=self.headers)
        res = json.loads(response.text)
        if 'errorMessage' in res:
            raise Exception('查询%s失败: ' + res['errorMessage'] % query_date)
        else:
            info = res['pageList'][0]
            self.projectCode = info['projectCode']
            status = info['status_Name']
            content = ''
            if 'content' in info:
                content = info['content'].replace(
                    info['projectCode'] + '@eq@', '')
            logger.info('查询%s成功: [%s][%s][%s]', query_date, status,
                        info['projectName'], info['projectCode'])
            logger.info('内容:\n%s', content)
            return status, content

    def save_log(self):
        '''
        保存周报
        '''
        params = {
            "staffId": self.staffId,
            "logRecordDate": self.weekdate,
            "workHours": self.weekhours,
            "logContents": self.projectCode + '@eq@' + self.content
        }
        response = self.session.post(
            self.save_url, data=params, headers=self.headers)
        res = json.loads(response.text)
        if res['errorMessage'] or res['logContents'].find(self.projectCode + '@eq@') < 0:
            logger.error('保存失败: ' + res['errorMessage'])
            raise Exception
        else:
            logger.info('保存成功')

    def submit_log(self):
        '''
        提交周报
        '''
        reg = re.compile('false', re.IGNORECASE)
        if not self.is_submit or reg.match(str(self.is_submit)):
            return
        params = {
            "staffId": self.staffId,
            "logRecordDate": self.weekdate,
            "workHours": self.weekhours,
            "logContents": self.projectCode + '@eq@' + self.content
        }
        response = self.session.post(
            self.submit_url, data=params, headers=self.headers)
        res = json.loads(response.text)
        if res['errorMessage'] or res['logContents'].find(self.projectCode + '@eq@') < 0:
            raise Exception('提交失败: ' + res['errorMessage'])
        else:
            logger.info('提交成功')

    def run(self):
        self.session = requests.Session()
        st = time.time()  # 记录开始时间
        try:
            self.load_config()
            self.login()
            _, content_last = self.query_log(
                self.today - datetime.timedelta(days=7))  # 查询上周内容
            status, content = self.query_log()  # 查询本周内容
            if content is not None and str.strip(content) != '':
                self.content = content  # 已填写内容
            elif content_last is not None and str.strip(content_last) != '':
                self.content = content_last  # 未填写内容取上周内容
            else:
                raise Exception('未查询到周报内容')
            if status == '已提交':
                logger.info('提交成功')
            else:
                self.save_log()
                self.submit_log()
        except requests.exceptions.ConnectionError:
            logger.error('网络连接失败')
        except Exception as e:
            logger.exception(e)
        t = time.time() - st  # 计算耗时时间
        logger.info('总耗时：%.2fs' % t)


if __name__ == '__main__':
    log_num = 20
    logger.info('*'*log_num + ' start ' + '*'*log_num)
    weekly_report = WeeklyReport()
    weekly_report.run()
    logger.info('*'*log_num + ' end ' + '*'*log_num)
    email = sendmail.Email()
    email.append_receivers(email.sender)
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        email.send('Weekly report schedule', f.read())
