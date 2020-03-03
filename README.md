![flashlight](flashlight.png)
# noting-analyzer
An audio transcriber for recordings of verbal noting meditation practices. If you are noting outloud to yourself you can transcribe those recordings using this tool. What you do with the output is up to you!

## Installation
`pip install -r requirements.txt`

## Usage
Ensure your AWS_ACCESS_KEY and AWS_SECRET_ACCESS_KEY are accessible to boto.

`python noting-analyzer.py <input file> <audio input s3 bucket> <audio transcription output bucket>`

sample output:
```
(...)
00000: there is congestion.
00003: there is breathing.
00006: there's anxiety.
00008: there is grasping.
00022: there is planning.
00036: there is thinking.
00043: there is breathing.
00048: there is discomfort.
00053: there's tiredness.
00060: there is closed.
00063: there is breathing.
00073: there's emptiness.
00077: they're sitting.
00080: there is anxious.
00090: there is pain.
00094: there's breathing.
00103: there is discomfort.
00104: they're straining.
```

## Caveats
* you are at the mercy of the AWS transcription service. It's not perfect!
* there's no cleanup. You'll need to setup a bucket policy or similar to delete old data.