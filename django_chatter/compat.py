try:
    from django.urls import re_path as path
except ImportError:  # django==1.11.xx
    from django.conf.urls import url as path
