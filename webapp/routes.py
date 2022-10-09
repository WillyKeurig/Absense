# builtins
from typing import List

# modules
import argon2.exceptions
from flask          import render_template, redirect, session, make_response, request
from flask_login    import login_user, current_user, logout_user

# import project
from webapp         import app, login_manager, ph, vd, VD, TH, Cf
from webapp.forms   import EmployeeFilter as EF
from webapp.forms   import *
from webapp.models  import *


###############
# HELPER FUNCTIONS

def get_employee_kwargs(
        form        : EmployeeFilterForm,
        students    : List['Student'],
    )-> dict:

    role    = session['filters']['role'] if \
        session['filters']['role'] != 'all' and \
        session['filters']['role'] is not None \
        else None

    group   = session['filters']['group'] != 'All' and \
              session['filters']['group'] is not None

    return {
        'form'      : form,
        'user'      : current_user,
        'students'  : students,
        'role'      : role,
        'group'     : group,
        'sort_by'   : session['filters']['sort_by'],
        'vd_default': vd.is_default(),
        'vd'        : vd,
    }


def render_template_no_cache(template, **context):
    """Mirrors render_template() but adds response headers that turns off caching"""
    response = make_response(render_template(template, **context))
    response.headers['Cache-Control'] = "no-cache, no-store, must-revalidate"
    return response


def session_init():
    try:
        x = session['login_attempt']  # raises E if non-existent
    except:
        session['login_attempt']    = False  # prevent first time visit alert
        session['user_prev']        = False  # save username for alert after cause form
        session['checkin_code']     = False  # check if student log fail/late/absent/present
        session['cause_redir']      = False  # different alerts if redirected from cause
        session['filters']          = {
            'group'     : None,
            'sort_by'   : None,
            'query'     : None,
            'role'      : None,
        }
        session.modified = True


@login_manager.user_loader
def load_user(email: str) -> TH.none_or(TH.user_clss):
    """Login user from email. Used for callback by flask_login module"""
    # Using email as id because there's a possibility of duplicate ids in the db.
    # To be able to store both user types separately in the db (to reduce size),
    # Student and Employee classes are decorated to use email lookups instead.
    return Student.from_email(email) or Employee.from_email(email)


###############
# VIEWS

@app.route('/clear')
@app.route('/clear/')
def clear_session():
    session.clear()
    return redirect('../student/login')


@app.route('/')
def landing_page():
    # If first visit, redirect to /help.
    # Keep session var to prevent more redirects
    session_init()
    return redirect('student/login')


@app.route('/student')
@app.route('/student/')
def student():
    session_init()
    logout_user()
    return redirect(url_for('student_login'))


@app.route('/student/login', methods=['GET', 'POST'])
@app.route('/student/login/', methods=['GET', 'POST'])
def student_login():
    """Student login page. Redirects to cause form page if student login succes."""

    # RUNTIME
    session_init()
    logout_user()

    # DECLARE
    def get_kwargs() -> dict:
        return {
            'form_login'    : StudentLoginForm(),
            'login_attempt' : session['login_attempt'],
            'user_prev'     : session['user_prev'],
            'checkin_code'  : session['checkin_code'],
            'vd'            : vd,
        }

    def get_kwargs_login() -> dict:
        """Return kwargs based on user. May also set vd.datetime. Return empty defaults if passed None."""

        hour_next_date  = None
        weekday         = None

        if current_user.group.hour_next_date():
            # get date next hour for alert
            hour_next_date = VD.comp_date(current_user.group.hour_next_date())

        if current_user.group.hour_next():
            # get weekday next hour for alert
            weekday = VD.weekday[current_user.group.hour_next().day_of_week].capitalize()

        return {
            'user'          : current_user.name_first,
            'form_login'    : StudentLoginForm(),
            'hour_now'      : current_user.group.hour_now(),  # currently expected
            'hour_next'     : current_user.group.hour_next(),  # next hour (can be tmrw)
            'hour_next_date': hour_next_date,
            'has_lessons'   : current_user.group.has_lessons(),  # is expected today
            'has_logged'    : False if Cf.demo else current_user.has_logged(),  # allow multiple logs per hr if demo
            'weekday'       : weekday,
            'is_off'        : current_user.group.is_off(),
            'login_attempt' : session['login_attempt'],
            'vd'            : vd,
        }

    def login_success(data: dict) -> bool:
        try:  # argon2.ph.verify raises exception if hash doesn't match
            user = load_user(data['email'])
            if ph.verify(user.password, data['password']):
                login_user(user)
                return True

        # pass if hash doesn't match (wrong pw) or student not found (reference attribute of NoneType)
        except (argon2.exceptions.VerifyMismatchError, AttributeError):
            print('Exception routes.student_login(): argon2.exceptions.VerifyMismatchError or AttributeError')
            return False

    # INIT
    form = StudentLoginForm()
    session['login_attempt'] = form.is_submitted()  # don't show alert if not attempted login

    # view return values
    tmpl_redirect_cause     = redirect(url_for('student_cause'))  # goto to cause
    tmpl_render_default     = render_template_no_cache('student/login.html', **get_kwargs())

    # POST
    if not form.validate_on_submit():
        return tmpl_render_default

    vd.process_form(form.data)  # extract dt from form (if submitted)

    # AUTHORIZE
    if not login_success(form.data):
        return tmpl_render_default

    # LOGIC
    if not current_user.group.hour_now():
        return render_template_no_cache('student/login.html', **get_kwargs_login())

    if current_user.group.is_late():
        return tmpl_redirect_cause

    # RETURN
    else:
        # Check in student
        current_user.check_in(vd.datetime)
        return render_template_no_cache('student/login.html', **get_kwargs_login())


@app.route('/student/cause', methods=['GET', 'POST'])
@app.route('/student/cause/', methods=['GET', 'POST'])
def student_cause():
    """Student lands here after checking in if the student is late."""

    # RUNTIME
    session_init()
    if not (current_user.is_authenticated or isinstance(current_user, Student)):
        # prevent access if not logged in as student. Redirect to /student/login
        return redirect(url_for('student_login'))

    # DECLARE
    def get_kwargs():
        mins_late   = current_user.group.mins_late()
        absent      = mins_late >= Cf.max_abs if mins_late else None
        return {
            'user'      : current_user.name_first,
            'form_cause': StudentCauseForm(),
            'hour_now'  : current_user.group.hour_now(),
            'hour_next' : current_user.group.hour_next(),  # next hour (can be tmrw)
            'vd_date'   : vd.date_str[2:],
            'vd_time'   : vd.time_str,
            'mins_late' : mins_late,
            'absent'    : absent,
            'max_abs'   : Cf.max_abs,
            'vd'        : vd,
        }

    # INIT
    form    = StudentCauseForm()

    # POST
    if form.validate_on_submit():
        # commit new Record to database if cause form meets requirements on POST
        session['checkin_code'] = current_user.check_in(
            datetime= vd.datetime,
            cause   = int(form.cause.data),
            reason  = form.reasoning.data,
        )
        session['user_prev'] = current_user.name_first
        return redirect(url_for('student_login'))

    # RETURN
    return render_template_no_cache('student/cause.html', **get_kwargs())


@app.route('/employee')
@app.route('/employee/')
def employee():
    session_init()
    logout_user()
    return redirect(url_for('employee_login'))


@app.route('/employee/login', methods=['GET', 'POST'])
@app.route('/employee/login/', methods=['GET', 'POST'])
def employee_login():

    # RUNTIME
    session_init()
    form = EmployeeLoginForm()

    # INIT
    def login_success(data: dict) -> bool:
        try:  # argon2.ph.verify raises exception if hash doesn't match (unauthorized)
            user = load_user(data['email'])
            if ph.verify(user.password, data['password']):
                login_user(user)
                return True

        # pass if hash doesn't match (wrong pw) or student not found (None.attr ref raises AttributeError)
        except (argon2.exceptions.VerifyMismatchError, AttributeError):
            print('Exception routes.student_login(): argon2.exceptions.VerifyMismatchError or AttributeError')
            return False

    # POST
    if form.validate_on_submit():
        if login_success(form.data):  # password match, user logged in
            return redirect(url_for('employee_overview'))
        else:
            return render_template_no_cache('employee/login.html', form=form, vd=vd, wrong_login=True)

    # RENDER
    return render_template_no_cache('employee/login.html', form=form, vd=vd)


@app.route('/employee/students', methods=['GET', 'POST'])
@app.route('/employee/students/', methods=['GET', 'POST'])
def employee_overview():

    # RUNTIME
    session_init()
    # prevent access if not logged in as employee, redir to login
    if not current_user.is_authenticated and not isinstance(current_user, Employee):
        return redirect(url_for('employee_login'))

    # DECLARE
    def set_filters(**kwargs):
        for kwarg in kwargs:
            session['filters'][kwarg] = kwargs[kwarg]
        session.modified = True

    def get_filters(*args):
        return [session['filters'][arg] for arg in args]

    def remember(form):
        form.group.data         = session['filters']['group']
        form.sort_by.data       = session['filters']['sort_by']
        form.query.data         = session['filters']['query']
        form.virtual_date.data  = vd.date_str if not vd.is_default_date() else None
        form.virtual_time.data  = vd.time_str if not vd.is_default_time() else None
        return form

    # INIT
    form = EmployeeFilterForm()
    role = request.args.get('role')  # role goes through GET redirect

    for group in current_user.groups:
        # populate show groups check-field
        form.group.choices.append(group.string)

    if not any(get_filters('group', 'sort_by', 'query')):
        # set filters to default on first visit
        set_filters(
            group   = form.group.choices[0],
            sort_by = form.sort_by.choices[0],
            query   = '',
        )

    # BREAKOUTS
    if role is not None:
        # set role through GET -> confirm if role belongs to user
        if role in [title.string for title in current_user.titles] or role == 'all':
            set_filters(role=role)
            return redirect(url_for('employee_overview'))


    # POST
    if form.validate_on_submit():
        # set filters based on form on submit and filter students
        vd.process_form(form.data)

        set_filters(
            group   = form.group.data,
            sort_by = form.sort_by.data,
            query   = form.query.data,
        )

    # LOGIC
    form = remember(form) # populate form data with selected filters

    students = EF.filtered(  # load filtered student list
        session['filters'],
        current_user,
        Student.query.all()
    )

    for student in students:
        student.update_status(vd.datetime)

    # RETURN
    return render_template_no_cache(
        'employee/students.html',
        **get_employee_kwargs(form, students)
    )


@app.route('/employee/students/<code>', methods=['GET', 'POST'])
@app.route('/employee/students/<code>/', methods=['GET', 'POST'])
def employee_student_details(code):

    # RUNTIME
    session_init()
    # prevent access if not logged in as employee, redir to login
    if not current_user.is_authenticated and not isinstance(current_user, Employee):
        return redirect(url_for('employee_login'))

    # DECLARE
    def get_kwargs():
        cause_count_late    = cause_count()[0]
        cause_count_absent  = cause_count()[1]

        amt_hours_all       = hours_in_year()
        amt_present         = len([rec for rec in records_past() if not rec.late])
        amt_late            = len([rec for rec in records_past() if rec.late and not rec.absent])
        amt_absent          = hours_in_year() - (amt_present + amt_late)
        amt_absent_known    = len([rec for rec in records_past() if rec.absent])
        amt_absent_unknown  = amt_absent - amt_absent_known

        percent_present     = round((amt_present / amt_hours_all) * 100)
        percent_late        = round((amt_late / amt_hours_all) * 100)
        percent_absent      = round((amt_absent / amt_hours_all) * 100)
        percent_sum_cent    = percent_present + percent_late + percent_absent == 100

        return {

            'student'           : student,
            'records'           : reversed(records_past()),
            'vd'                : vd,
            'cf_max_late'       : Cf.max_late,
            'user'              : current_user,
            'total_recs'        : hours_in_year(),
            'records_len'       : len(records_past()),
            'form'              : form,
            'vd_default'        : vd.is_default(),

            'cause_count_late'  : cause_count_late,
            'cause_count_absent': cause_count_absent,

            'amt_hours_all'     : amt_hours_all,
            'amt_present'       : amt_present,
            'amt_late'          : amt_late,
            'amt_absent'        : amt_absent,
            'amt_absent_known'  : amt_absent_known,
            'amt_absent_unknown': amt_absent_unknown,

            'percent_present'   : percent_present,
            'percent_late'      : percent_late,
            'percent_absent'    : percent_absent,
            'percent_sum_cent'  : percent_sum_cent,
        }

    def get_kwargs_no_recs():
        return {
            'form'              : DatetimeForm(),
            'student'           : student,
            'records'           : [],
            'vd'                : vd,
            'vd_default'        : vd.is_default(),
            'cf_max_late'       : Cf.max_late,
            'user'              : current_user,

            'amt_hours_all'     : hours_in_year(),
            'amt_records'       : 0,
            'amt_late'          : 0,
            'amt_absent'        : hours_in_year(),
            'amt_absent_known'  : 0,
            'amt_absent_unknown': hours_in_year(),
            'cause_count_late'  : {},
            'cause_count_absent': {},

            'percent_present'   : 0,
            'percent_late'      : 0,
            'percent_absent'    : 100,
            'percent_sum_cent'  : 1,
        }

    def records_past():
        recs = []
        for rec in records:
            if dt.datetime.combine(VD.parse_date(rec.date), VD.parse_time(rec.time)) <= vd.datetime:
                recs.append(rec)

        return sorted(recs, key=lambda rec: dt.datetime.combine(VD.parse_date(rec.date), VD.parse_time(rec.time)))

    def hours_in_year():

        hours   = 0
        date    = VD.parse_date(Cf.year_start)


        # iterate days from year_start < today, add hours in day
        while date != vd.date:
            if student.group.hours_on_date(date):
                hours += len(student.group.hours_on_date(date))
            date += dt.timedelta(days=1)

        # only append past hours of today
        for hour in student.group.hours_on_date(vd.date):
            hour_start = dt.datetime.combine(vd.date, VD.parse_time(hour.time_start))
            if hour_start < vd.datetime:
                hours += 1

        return hours

    def cause_count():
        cause_count_late    = {}
        cause_count_absent  = {}

        for rec in records_past():
            # rec_dt = dt.datetime.combine(vd.date, VD.parse_time(rec.time))
            if rec.late and not rec.absent:
                try:
                    cause_count_late[rec.cause.string] += 1
                except:
                    cause_count_late[rec.cause.string] = 1
            elif rec.absent:
                try:
                    cause_count_absent[rec.cause.string] += 1
                except:
                    cause_count_absent[rec.cause.string] = 1

        return [cause_count_late, cause_count_absent]

    # INIT
    student = Student.from_code(code)
    records = Record.query.filter_by(student_id = student.id).all()
    form    = DatetimeForm()

    # POST
    if form.validate_on_submit():
        vd.process_form(form.data)  # set vd from form

    # remember
    form.virtual_date.data = vd.date_str if not vd.is_default_date() else None
    form.virtual_time.data = vd.time_str if not vd.is_default_time() else None


    # RETURN
    if not records_past():
        return render_template_no_cache('employee/details.html', **get_kwargs_no_recs())

    return render_template_no_cache('employee/details.html', **get_kwargs())