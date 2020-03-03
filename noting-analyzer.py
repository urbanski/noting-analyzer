#!/usr/bin/env python3

import uuid
import tempfile
import boto3
import argparse
import sys
import logging
import time
import json

from pydub import AudioSegment
from pydub.silence import split_on_silence
from botocore.exceptions import ClientError


def upload_file(file_name, bucket, object_name=None):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False

    ref: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html
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


def run(input_file, input_bucket, output_bucket, silence_ms):
    # setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)-15s %(levelname)s %(message)s')

    # create a temporary local directory
    tempdir = tempfile.mkdtemp()

    # create a "job id"
    job_id = uuid.uuid4()

    max_chunks = 0  # the total number of audio chunks observed at any dBM rating.
    dbm = 0         # the dBM to use

    # read the audio file
    sound_file = AudioSegment.from_file(sys.argv[1])

    # determine an optimal dBM value to use
    logging.info("Sound average DBFS is %d", sound_file.dBFS)
    logging.info("Looking for an optimal dBM value...")

    dbm_chunks = {}
    for i in range(1, 4):

        dbm_test = sound_file.dBFS - (i * .5)
        audio_chunks = split_on_silence(sound_file,
            min_silence_len = silence_ms,
            silence_thresh = dbm_test
        )

        dbm_chunks[dbm_test] = audio_chunks

        if len(audio_chunks) > max_chunks:
            max_chunks = len(audio_chunks)
            dbm = dbm_test

        logging.info("Computed audio chunks @ %d dBM: %d", dbm_test, len(audio_chunks))

    logging.info("Using %d dBM", dbm)
    audio_chunks = dbm_chunks[dbm]

    xc_job_ids = [] # for storing transcription job ids
    xclient = boto3.client('transcribe')

    for i, chunk in enumerate(audio_chunks):

        # export an mp3 of the chunk to the local filesystem
        out_file = "{0}/chunk{1}.mp3".format(tempdir, i)
        logging.info("exporting %s", out_file)
        chunk.export(out_file, format="mp3")

        s3path = "%s/%s.mp3" % (job_id, str(i).zfill(5))
        s3fullpath = "s3://%s/%s" % (input_bucket, s3path)

        logging.info("Uploading %s", s3path)
        upload_file(out_file, input_bucket, s3path)

        transcribe_job_id = "%s-%s" % (job_id, str(i).zfill(5))
        xc_job_ids.append(transcribe_job_id)

        # queue the transcription job
        response = xclient.start_transcription_job(
            TranscriptionJobName= transcribe_job_id,
            LanguageCode='en-US',
            MediaFormat='mp3',
            Media={
                'MediaFileUri': s3fullpath
            },

            OutputBucketName=output_bucket
        )

    # collect the transcriptions
    transcriptions = {}
    done_ids = []
    s3 = boto3.resource('s3')
    while len(xc_job_ids) > 0:
        sleeptime = 5
        logging.info("Sleeping for %d seconds while waiting for transcription..." % sleeptime)
        time.sleep(sleeptime)
        for j in xc_job_ids:
            status = xclient.get_transcription_job(TranscriptionJobName = j)
            if status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
                logging.info("Transcription job %s is done", j)

                obj = s3.Object(output_bucket, "%s.json" % j)
                raw_json = obj.get()['Body'].read().decode('utf-8')
                jobj = json.loads(raw_json)

                # job is finished. we can stop tracking it.
                xc_job_ids.remove(j)

                # grab the ordering id
                order_id = j.split("-")[-1]
                transcript = jobj['results']['transcripts'][0]['transcript']
                transcriptions[order_id] = transcript
                print("%s: %s" % (j, transcript))
        if len(xc_job_ids) > 0:
            logging.info("Still waiting on %s transcriptions: %s", len(xc_job_ids), ",".join(xc_job_ids))

    # print all the transcriptions to the screen
    for i in sorted (transcriptions.keys()):
        transcribed_text = transcriptions[i]
        if transcribed_text != "":
            print("%s: %s" % (i, transcribed_text))

    json_output = {'notes': transcriptions}
    print(json.dumps(json_output))


def main():
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('file', type=str, action='store',
                        help='input file (MP3, M4A, AAC, or WAV)')
    parser.add_argument('input_bucket', action='store',
                        help='audio input s3 bucket')
    parser.add_argument('output_bucket', action='store',
                        help='transcription output s3 bucket')
    parser.add_argument('--silence', dest='silence', action='store',
                        type=int, default=2000, required=False,
                        help='silence detection value (ms)')
    args = parser.parse_args()
    run(args.file, args.input_bucket, args.output_bucket, args.silence)


if __name__ == "__main__":
    main()
