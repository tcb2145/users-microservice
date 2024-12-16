import requests
import logging
import time
import os
import uuid
from fastapi import Request, FastAPI
try:
    from google.cloud import logging as gcp_logging
except ImportError:
    gcp_logging = None

CORRELATION_ID_HEADER = "X-Correlation-ID"

class Logger:
    _instance = None
    _gcp_logging_client = None

    # Singleton pattern
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance
        
    def __init__(self, app: FastAPI = None, service_name: str = "MyService"):
        if not hasattr(self, 'initialized'):  # To prevent re-initializing
            self.initialized = True
            self.service_name = service_name
            
            # Use FastAPI's logger if provided
            if app and hasattr(app, 'logger'):
                self._internal_logger = app.logger
            else:
                self._internal_logger = logging.getLogger(self.service_name)
                self._internal_logger.setLevel(logging.INFO)
            
            # Initialize GCP logging client (if not already done)
            if Logger._gcp_logging_client is None:
                try:
                    Logger._gcp_logging_client = gcp_logging.Client()
                    Logger._gcp_logging_client.setup_logging()
                except Exception as e:
                    self._internal_logger.error(f"Failed to setup GCP Logging: {e}")
                    Logger._gcp_logging_client = None

    async def log_request(self, request_path: str, response_status: int, process_time: int, correlation_id: str):
        
        logger_type = 'cloud' if Logger._gcp_logging_client is not None else 'local'
        
        log_data = {
            'service': self.service_name,
            'message': f'Request logged from {logger_type} logger',
            'request_path': request_path,
            'response_status': response_status,
            'process_time': process_time,
            'correlation_id': correlation_id
        }
        
        self._internal_logger.info(log_data)


    async def log_message(self, message: str):
        # Log a custom message
        self._internal_logger.info(message)