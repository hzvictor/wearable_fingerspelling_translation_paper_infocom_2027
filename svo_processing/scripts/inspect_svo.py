"""Quick MCAP structural inspector. Prints schemas, channels, per-channel counts,
and the embedded calibration JSON from svo_header."""
import argparse
import json
import sys
from pathlib import Path
from mcap.reader import make_reader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("svo", type=Path)
    args = p.parse_args()

    with open(args.svo, "rb") as f:
        reader = make_reader(f)
        summary = reader.get_summary()

        print(f"=== {args.svo} ===")
        print(f"metadata indexes: {len(summary.metadata_indexes)}  "
              f"attachments: {len(summary.attachment_indexes)}")

        print("\nSchemas:")
        for sid, schema in summary.schemas.items():
            print(f"  [{sid}] name={schema.name!r}  encoding={schema.encoding!r}  "
                  f"data_len={len(schema.data)}")

        print("\nChannels:")
        for cid, ch in summary.channels.items():
            print(f"  [{cid}] topic={ch.topic!r}  "
                  f"schema={summary.schemas[ch.schema_id].name!r}  "
                  f"encoding={ch.message_encoding!r}")

        if summary.statistics:
            s = summary.statistics
            print(f"\nStats:")
            print(f"  messages={s.message_count}  "
                  f"duration={(s.message_end_time - s.message_start_time)/1e9:.2f}s")
            print(f"  per-channel:")
            for cid, cnt in s.channel_message_counts.items():
                topic = summary.channels[cid].topic
                print(f"    {cnt:8d}  {topic}")

        print("\nsvo_header (calibration JSON):")
        for sch, ch, msg in reader.iter_messages(topics=["svo_header"]):
            try:
                j = json.loads(msg.data.decode("utf-8", "replace"))
                snippet = {k: (v if not isinstance(v, str) or len(v) < 60 else v[:57] + "...")
                           for k, v in j.items()}
                print(json.dumps(snippet, indent=2))
            except Exception as e:
                print(f"  parse failed: {e}")
            break


if __name__ == "__main__":
    main()
