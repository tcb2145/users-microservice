FROM python:3.9
WORKDIR /code
# Copy the common directory first
COPY common/ /code/common/
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./app.py /code/
EXPOSE 8000
CMD ["python", "app.py"]