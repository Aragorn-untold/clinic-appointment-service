

def cancel_appointment(appointment, request=None):
    raise NotImplementedError

def complete_appointment(appointment, request=None):
    raise NotImplementedError

def mark_no_show(appointment, request=None): # вызывается из эндпоинта и из ежедневной задачи
    raise NotImplementedError
