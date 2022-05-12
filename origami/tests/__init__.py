import warnings

# The asynctest library has backwards compatibility for older pythons that emit a lot of warnings
warnings.filterwarnings(action='ignore', category=DeprecationWarning, module=r'.*asynctest')
