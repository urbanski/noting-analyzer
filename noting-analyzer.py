
import uuid
import os
import tempfile

from pydub import AudioSegment
from pydub.silence import split_on_silence

import logging
import boto3
import sys
import logging
import time
import json
from botocore.exceptions import ClientError


def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True


tempdir = tempfile.mkdtemp()
job_id = uuid.uuid4()

sound_file = AudioSegment.from_mp3(sys.argv[1])
audio_chunks = split_on_silence(sound_file,
    min_silence_len = 2000,
    silence_thresh = -50
)

logging.basicConfig(level=logging.INFO)
logging.info("Got %s audio chunks", len(audio_chunks))

xc_job_ids = []
xclient = boto3.client('transcribe')

for i, chunk in enumerate(audio_chunks):
    out_file =  "{0}/chunk{1}.mp3".format(tempdir, i)
    logging.info("exporting %s", out_file)
    chunk.export(out_file, format="mp3")

    s3path = "%s/%s.mp3" % (job_id, str(i).zfill(5))

    s3fullpath = "s3://noting-inputs/%s" % s3path

    logging.info("Uploading %s", s3path)
    upload_file(out_file, "noting-inputs", s3path)

    transcribe_job_id = "%s-%s" % (job_id, str(i).zfill(5))

    xc_job_ids.append(transcribe_job_id)

    response = xclient.start_transcription_job(
        TranscriptionJobName= transcribe_job_id,
        LanguageCode='en-US',
        MediaFormat='mp3',
        Media={
            'MediaFileUri': s3fullpath
        },
        OutputBucketName='noting-transcribe-output'
    )
    #print(response)

transcriptions = {}
done_ids = []
while len(xc_job_ids) > 0:
    sleeptime = 5
    logging.info("Sleeping for %d seconds while waiting for transcription..." % sleeptime)
    time.sleep(sleeptime)
    for j in xc_job_ids:
        status = xclient.get_transcription_job(TranscriptionJobName = j)
        if status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
            logging.info("Transcription job %s is done", j)
            s3 = boto3.resource('s3')
            obj = s3.Object("noting-transcribe-output", "%s.json" % j)
            print(obj.get()['Body'].read().decode('utf-8'))

            raw_json = obj.get()['Body'].read().decode('utf-8')
            jobj = json.loads(raw_json)

            xc_job_ids.remove(j)

            order_id = j.split("-")[-1]

            transcript = jobj['results']['transcripts'][0]['transcript']
            transcriptions[order_id] = transcript
            print("%s: %s" % (j, transcript))
    logging.info("Still waiting on %s transcriptions: %s", len(xc_job_ids), ",".join(xc_job_ids))

for i in sorted (transcriptions.keys()):
     print("%s: %s" % (i, transcriptions[i]))