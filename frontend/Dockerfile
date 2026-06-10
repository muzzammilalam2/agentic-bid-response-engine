FROM python:3.11-slim

WORKDIR /app

# Install Streamlit and requests
RUN pip install --no-cache-dir streamlit requests

# Copy source files
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
