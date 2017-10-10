# These targets are not files
.PHONY: install messages compiledmessages css clean

install:
	pip install -e . -r requirements.txt

messages:
	# Create the .po files used for i18n
	cd src/oscar; django-admin.py makemessages -a

compiledmessages:
	# Compile the gettext files
	cd src/oscar; django-admin.py compilemessages

css:
	# Compile CSS files from LESS
	lessc --source-map --source-map-less-inline src/oscar/static/oscar/less/styles.less src/oscar/static/oscar/css/styles.css
	lessc --source-map --source-map-less-inline src/oscar/static/oscar/less/responsive.less src/oscar/static/oscar/css/responsive.css
	lessc --source-map --source-map-less-inline src/oscar/static/oscar/less/dashboard.less src/oscar/static/oscar/css/dashboard.css

clean:
	# Remove files not in source control
	find . -type f -name "*.pyc" -delete
	rm -rf nosetests.xml coverage.xml htmlcov *.egg-info *.pdf dist violations.txt
