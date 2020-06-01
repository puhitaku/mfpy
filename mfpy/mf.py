from __future__ import annotations

import enum
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import ContextManager, List, Optional, Tuple

import requests as req
from bs4 import BeautifulSoup as bsOrig
from urlpath import URL

from mfpy.model import TimeEntry

bs = partial(bsOrig, features='html.parser')  # Chill, chill...
path = URL('https://attendance.moneyforward.com/')


@contextmanager
def client(company_id, user_id, password) -> ContextManager[_Client]:
    """Establish a session between MF server and return a client. """

    try:
        sess, status = _establish(company_id, user_id, password)
        if not sess:
            raise RuntimeError('Failed to login to MF:', status)
        yield _Client(sess)
    finally:
        pass


@dataclass
class _MFSession:
    session_id: str
    employee_id: str
    location_id: str


class _Ops(enum.Enum):
    clock_in = 'clock_in'
    clock_out = 'clock_out'
    start_break = 'start_break'
    end_break = 'end_break'


class _Client:
    _sess: _MFSession

    def __init__(self, sess):
        self._sess = sess

    def post_entries(self, entries: List[TimeEntry]) -> Tuple[bool, int]:
        """Post one or more time entries.

        Args:
            entries: a list of TimeEntry. See mfpy.model.TimeEntry for details.

        Returns:
            bool: Succeeded or not.
            int: HTTP status code.
        """

        attendances_url = path / 'my_page' / 'attendances'
        date = entries[0].start.date()

        # 1. GET attendances/YYYY-MM-DD/edit
        edit_url = attendances_url / date.strftime("%Y-%m-%d") / 'edit'
        cookies = {'_session_id': self._sess.session_id}

        edit = req.request('GET', edit_url, cookies=cookies)
        if not edit.ok:
            return False, edit.status_code

        form_csrf_token = bs(edit.content.decode()).find('input', attrs={'name': 'authenticity_token'}).attrs[
            'value']

        # 2. POST attendances/YYYY-MM-DD
        attendances_post_url = attendances_url / date.strftime("%Y-%m-%d")
        params = {'employee_id': str(self._sess.employee_id)}
        form = {
            '_method': 'put',
            'authenticity_token': form_csrf_token,
            'attendance_schedule_form[start_time]': '',
            'attendance_schedule_form[end_time]': '',
            'attendance_schedule_form[attendance_form_attributes][note]': '',
            'commit': '保存',
        }

        for i, entry in enumerate(entries):
            k = f'attendance_schedule_form[attendance_record_forms_attributes]'
            if len(entries) == 1:
                ev_start, ev_stop = 'clock_in', 'clock_out'
            elif i == 0:
                ev_start, ev_stop = 'clock_in', 'start_break'
            elif i == len(entries) - 1:
                ev_start, ev_stop = 'end_break', 'clock_out'
            else:
                ev_start, ev_stop = 'end_break', 'start_break'

            form[k + f'[{i * 2 + 0}][event]'] = ev_start
            form[k + f'[{i * 2 + 0}][_destroy]'] = 'false'
            form[k + f'[{i * 2 + 0}][date]'] = entry.start.strftime('%Y-%m-%d')
            form[k + f'[{i * 2 + 0}][time]'] = entry.start.strftime('%H:%M')
            form[k + f'[{i * 2 + 0}][attendance_record_id]'] = ''
            form[k + f'[{i * 2 + 0}][office_location_id]'] = self._sess.location_id

            form[k + f'[{i * 2 + 1}][event]'] = ev_stop
            form[k + f'[{i * 2 + 1}][_destroy]'] = 'false'
            form[k + f'[{i * 2 + 1}][date]'] = entry.stop.strftime('%Y-%m-%d')
            form[k + f'[{i * 2 + 1}][time]'] = entry.stop.strftime('%H:%M')
            form[k + f'[{i * 2 + 1}][attendance_record_id]'] = ''
            form[k + f'[{i * 2 + 1}][office_location_id]'] = self._sess.location_id

        attendances_post = req.request('POST', attendances_post_url, params=params, cookies=cookies, data=form)
        if not attendances_post.ok:
            return False, attendances_post.status_code

        return True, attendances_post.status_code

    def start_job(self) -> Tuple[bool, int]:
        """ Record "start job (clock in)".

        Returns:
            bool: Succeeded or not.
            int: HTTP status code.
        """
        return self._record(_Ops.clock_in)

    def finish_job(self) -> Tuple[bool, int]:
        """ Record "finish job (clock out)".

        Returns:
            bool: Succeeded or not.
            int: HTTP status code.
        """
        return self._record(_Ops.clock_out)

    def start_break(self) -> Tuple[bool, int]:
        """ Record "start break".

        Returns:
            bool: Succeeded or not.
            int: HTTP status code.
        """
        return self._record(_Ops.start_break)

    def finish_break(self) -> Tuple[bool, int]:
        """ Record "finish break (end break)".

        Returns:
            bool: Succeeded or not.
            int: HTTP status code.
        """
        return self._record(_Ops.end_break)

    def _record(self, op: _Ops) -> Tuple[bool, int]:
        mypage_url = URL('https://attendance.moneyforward.com/my_page')

        # 1. GET my_page and scrape authenticity_token
        cookies = {'_session_id': self._sess.session_id}
        mypage = req.request('GET', mypage_url, cookies=cookies)
        if not mypage.ok:
            return False, mypage.status_code

        mbs = bs(mypage.content.decode())
        clock_in = mbs.find('input', attrs={'value': 'clock_in'}).parent
        clock_out = mbs.find('input', attrs={'value': 'clock_out'}).parent
        start_break = mbs.find('input', attrs={'value': 'start_break'}).parent
        end_break = mbs.find('input', attrs={'value': 'end_break'}).parent
        auths = {
            _Ops.clock_in: clock_in.find('input', attrs={'name': 'authenticity_token'}).attrs['value'],
            _Ops.clock_out: clock_out.find('input', attrs={'name': 'authenticity_token'}).attrs['value'],
            _Ops.start_break: start_break.find('input', attrs={'name': 'authenticity_token'}).attrs['value'],
            _Ops.end_break: end_break.find('input', attrs={'name': 'authenticity_token'}).attrs['value'],
        }

        # 2. POST time record
        web_time_recorder_url = path / 'my_page' / 'web_time_recorder'
        cookies = {'_session_id': self._sess.session_id}

        d = datetime.utcnow()

        form = {
            'authenticity_token': auths[op],
            'web_time_recorder_form[event]': op.value,
            'web_time_recorder_form[date]': f'{d.year}/{d.month}/{d.day}',
            'web_time_recorder_form[user_time]': d.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'web_time_recorder_form[office_location_id]': self._sess.location_id,
        }

        recorder = req.request('POST', web_time_recorder_url, cookies=cookies, data=form)
        return recorder.ok, recorder.status_code


def _establish(office_account_name, email, password) -> Tuple[Optional[_MFSession], int]:
    employee_session_url = URL('https://attendance.moneyforward.com/employee_session')
    new_url = employee_session_url / 'new'

    # 1. Login
    new = req.get(new_url)
    if not new.ok:
        return None, new.status_code

    cookies = {'_session_id': new.cookies['_session_id']}

    authenticity_token = bs(new.content.decode()).find('input', attrs={'name': 'authenticity_token'}).attrs['value']
    form = {
        'authenticity_token': authenticity_token,
        'employee_session_form[office_account_name]': office_account_name,
        'employee_session_form[account_name_or_email]': email,
        'employee_session_form[password]': password,
    }

    login = req.post(employee_session_url, cookies=cookies, data=form, allow_redirects=False)
    if not login.ok:
        return None, login.status_code

    # 2. Redirect
    cookies = {'_session_id': login.cookies['_session_id']}  # Use the new session_id
    mypage = req.get(login.next.url, cookies=cookies)
    if not mypage.ok:
        return None, mypage.status_code

    mybs = bs(mypage.content.decode())

    return _MFSession(
        session_id=mypage.cookies['_session_id'],
        employee_id=mybs.find('meta', attrs={'name': 'js:rollbar:uid'}).attrs['content'],
        location_id=mybs.find('input', attrs={'id': 'web_time_recorder_form_office_location_id'}).attrs['value'],
    ), mypage.status_code
