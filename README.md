# EV Charging Station API

A FastAPI-based EV charging station management system implementing OCPP 1.6 protocol.

## Features

- OCPP 1.6 protocol implementation
- WebSocket server for charger communication
- REST API endpoints for charger management
- Real-time charger status monitoring
- Session management
- Third-party API integration

## Deployment on Render

1. Fork this repository to your GitHub account
2. Sign up for a Render account at https://render.com
3. Click "New +" and select "Web Service"
4. Connect your GitHub repository
5. Configure the service:
   - Name: ev-charging-api (or your preferred name)
   - Environment: Docker
   - Branch: main
   - Plan: Free
6. Click "Create Web Service"

The application will be automatically deployed and you'll get a URL where your API is accessible.

## Local Development

1. Clone the repository:
```bash
git clone <your-repo-url>
cd ev-charging
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
uvicorn main:app --reload
```

The API will be available at http://localhost:8000

## API Documentation

Once the application is running, you can access:
- Interactive API documentation: http://localhost:8000/docs
- Alternative API documentation: http://localhost:8000/redoc

## Environment Variables

The following environment variables can be configured:
- `PORT`: The port number to run the server on (default: 8000)
- `PYTHON_VERSION`: Python version to use (default: 3.11.0)

## License

MIT 