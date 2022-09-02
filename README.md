# biogeek.github.io
Personal website https://jeroen.vangoey.be

# To deploy

```
$ git clone git@github.com:BioGeek/biogeek.github.io.git
$ git checkout -b source
$ curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash
$ nvm install node
$ npm install
$ npm audit fix --force
$ npm run develop
# See local version at http://localhost:8000/
$ git add .
$ git commit -m "Add new job info"
$ git push
$ npm run deploy

```
