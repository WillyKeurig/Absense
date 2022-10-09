from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, PasswordField, BooleanField, SubmitField, TextAreaField
from wtforms.validators import DataRequired
from webapp import db, Cf, Title


class LoginForm(FlaskForm):
    email           = StringField(
        'E-mail',
        render_kw   = {'placeholder': 'Email'},
        validators  = [DataRequired()],
    )
    password        = PasswordField(
        'Password',
        render_kw   = {'placeholder': 'Password'},
        validators  = [DataRequired()],
    )
    submit          = SubmitField('LOG IN')


class StudentLoginForm(LoginForm):
    email           = StringField(
        'E-mail',
        render_kw   = {'placeholder': 'Email/Code', 'value': '21683239@school.nl'},
        validators  = [DataRequired()],
    )
    virtual_date    = StringField(
        'Virtual Date',
        render_kw   = {'placeholder': Cf.d_str[2:].replace('/', '-')}
    )
    virtual_time    = StringField(
        'Virtual Time',
        render_kw   = {'placeholder': Cf.t_str}
    )
    submit          = SubmitField('CHECK IN')


class EmployeeLoginForm(LoginForm):
    email           = StringField(
        'E-mail',
        render_kw   = {'placeholder': 'Email/Code', 'value': 'm.vosteen@school.nl'},
        validators  = [DataRequired()],
    )


sff_sort_choices = ['voornaam', 'achternaam']
sff_klas_choices = []


class DatetimeForm(FlaskForm):
    virtual_date    = StringField('Date', render_kw={'placeholder': Cf.d_str[2:].replace('/', '-')})
    virtual_time    = StringField('Time', render_kw={'placeholder': Cf.t_str})
    submit          = SubmitField('Set')


class EmployeeFilterForm(FlaskForm):
    group           = SelectField('Group', choices=['All'])
    sort_by         = SelectField('Sort', choices=[
        'Checked in', 'Group', 'First name', 'Last name'
    ])
    role            = 'None'
    virtual_date    = StringField('Date', render_kw={'placeholder': Cf.d_str[2:].replace('/', '-')})
    virtual_time    = StringField('Time', render_kw={'placeholder': Cf.t_str})
    query           = StringField('Query', render_kw={'placeholder': 'Student name/code'})

    submit          = SubmitField('Search')


class EmployeeFilter:

    @staticmethod
    def filtered(filters, employee, students):
        students = EmployeeFilter.authorize(employee, students)  # remove students not allowed
        students = EmployeeFilter.filter(filters, students)      # remove students not looking for
        students = EmployeeFilter.sort(filters, students)        # order list
        return students

    @staticmethod
    def includes(title, student):

        def match_year(title, student):
            """Return True if Title includes Student's year"""
            return True if title.year in [None, student.year] else False

        def match_level(title, student):
            """Return True if Title includes Student's level"""
            return True if title.level in [None, student.level] else False

        def match_senior(title, student):
            """Return True if Title includes Student's senior status"""
            if title.senior is None:
                return True
            else:
                senior = True if student.year >= Cf.senior else False
                return title.senior == senior

        return True if all([
            match_year(title, student),
            match_level(title, student),
            match_senior(title, student)
        ])  else False

    @staticmethod
    def authorize(employee, students):

        for title in employee.titles:
            if title.admin:  # skip filter if admin
                return students

        for s in reversed(students):  # iter student first to allow .pop()
            match = False  # catch

            for t in employee.titles:              # for title:
                if EmployeeFilter.includes(t, s):  # check for student inclusion
                    match = True
                    break

            if not match:
                students.remove(s)

        return students


    @staticmethod
    def filter(filters, students):

        def group_match(s):
            return filters['group'] == s.group.string

        def role_match(s):
            r = Title.from_string(filters['role'])
            return EmployeeFilter.includes(r, s)

        def query_match(s):
            return any([
                filters['query'].casefold() in s.name().casefold(),
                filters['query'] in s.code,
            ])

        def cf(str):
            return None if str is None else str.casefold()

        # if filters have value and not default, use for matching
        match_funcs = []
        wildcards = [None, '', 'all'.casefold()]
        if not cf(filters['role']) in wildcards:
            match_funcs.append(role_match)
        if not cf(filters['group']) in wildcards:
            match_funcs.append(group_match)
        if not cf(filters['query']) in wildcards:
            match_funcs.append(query_match)

        # remove students that don't meet all match_func requirements
        for s in reversed(students):
            if not all([f(s) for f in match_funcs]):
                students.remove(s)

        return students

    @staticmethod
    def sort(filters, students):

        if filters['sort_by'] == 'Group':
            return sorted(students, key=lambda student: (student.group.string, student.name_first))
        if filters['sort_by'] == 'First name':
            return sorted(students, key=lambda student: (student.name_first, student.group.string))
        elif filters['sort_by'] == 'Last name':
            return sorted(students, key=lambda student: (student.name_last, student.group.string))
        else:
            # default set unexpected last
            not_expected = []
            for student in reversed(students):
                if not student.group.hour_now():
                    not_expected.append(students.pop(students.index(student)))  # use pop for return value of popped

            sort = sorted(students, key=lambda student: (not student.has_logged(), student.group.string, student.name_first))
            for student in sorted(not_expected, key=lambda student: (student.group.string, student.name_first)):
                sort.append(student)

            return sort


class StudentCauseForm(FlaskForm):

    @staticmethod
    def get_choices():
        """List[Tuple[int, str]] -> List[Tuple[str, str]]
        New format is needed to populate choices in form"""
        tup_str = []
        tup_int = db.session.execute("""SELECT * FROM cause""").all()
        for tup in tup_int:
            tup_str.append((str(tup[0]), tup[1]))
        return tup_str

    cause           = SelectField(
        'Cause',
        validators  = [DataRequired()],
        choices     = get_choices(),
    )
    reasoning       = TextAreaField(
        'Reasoning',
        render_kw   = {'placeholder': 'Reason'}
    )
    submit          = SubmitField('OK')
