1  git --version
    2  sudo apt update
    3  git --version
    4  sudo apt install git -y
    5  git --version
    6  git clone https://github.com/shantanushubham/PythonC22.git
    7  cd PythonC22/
    8  cd ledger_project/
    9  curl -sSf https://astral.sh/uv/install.sh | sh
   10  cd ../../
   11  curl -sSf https://astral.sh/uv/install.sh | sh
   12  sudo apt update && sudo apt install curl -y
   13  curl -LsSf https://astral.sh/uv/install.sh | sh
   14  source $HOME/.local/bin/env 
   15  cd PythonC22/ledger_project/
   16  uv sync
   17  source .venv/bin/activate
   18  sudo apt update
   19  sudo apt install postgresql postgresql-contrib -y
   20  sudo systemctl start postgresql
   21  sudo systemctl enable postgresql
   22  sudo -i -u postgres
   23  sudo systemctl start redis-server
   24  sudo systemctl enable redis-server
   25  sudo apt install redis-server -y
   26  sudo systemctl start redis-server
   27  sudo systemctl enable redis-server
   28  redis-cli ping
   29  touch .env
   30  cat .env
   31  vi .env
   32  python manage.py makemigrations
   33  sudo -i -u postgres psql
   34  python manage.py makemigrations
   35  python manage.py migrate
   36  uvicorn config.asgi:application
   37  sudo -i -u postgres psql
   38  uvicorn config.asgi:application
   39  uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload
   40  git fetch && git pull
   41  vi .env
   42  uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload
   43  cd ../
   44  cd PythonC22/
   45  ls
   46  cd payment_gateway_node/
   47  node --version
   48  curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
   49  sudo apt install -y nodejs
   50  node -v
   51  npm -v
   52  npm install
   53  npm start
   54  cat package.json 
   55  npm run build
   56  npm start
   57  nohup npm start &
   58  cd ../ledger_project/
   59  uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload
   60  git fetch && git pull
   61  uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload
   62  git fetch && git pull
   63  nohup uv run celery -A config worker --loglevel=INFO -P=solo &
   64  uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload



Gemini Conversation: https://share.gemini.google/4Thze2okVhVo