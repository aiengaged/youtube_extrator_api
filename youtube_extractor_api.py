from flask import Flask, request, jsonify
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import json
import os
import logging

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Function to extract YouTube transcript
def extract_youtube_transcript(video_id):
    try:
        # Fetch the YouTube video page
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {"error": "Failed to fetch YouTube video page"}, 400

        # Parse the page content
        soup = BeautifulSoup(response.text, "html.parser")

        # Find the script tag containing the transcript data
        scripts = soup.find_all("script")
        transcript_data = None
        for script in scripts:
            if "ytInitialPlayerResponse" in script.text:
                transcript_data = script.text
                break

        if not transcript_data:
            return {"error": "Transcript data not found"}, 404

        # Extract the JSON data
        match = re.search(r"ytInitialPlayerResponse\s*=\s*({.*?});", transcript_data)
        if not match:
            return {"error": "Failed to extract JSON data"}, 400

        json_data = json.loads(match.group(1))

        # Extract captions from the JSON data
        captions = json_data.get("captions", {}).get("playerCaptionsTracklistRenderer", {}).get("captionTracks", [])

        # Debug: Log captions for inspection
        logging.info(f"Captions found: {json.dumps(captions, indent=2)}")

        # Check for captions
        if not captions:
            return {"error": "No captions found (manual or auto-generated)"}, 404

        # Check for auto-generated captions (kind: "asr")
        auto_generated_captions = [
            track for track in captions if "kind" in track and track["kind"] == "asr"
        ]

        # Prefer auto-generated captions if available
        if auto_generated_captions:
            logging.info("Using auto-generated captions.")
            caption_url = auto_generated_captions[0].get("baseUrl")
        else:
            logging.info("Using manually provided captions.")
            caption_url = captions[0].get("baseUrl")

        # Ensure a caption URL exists
        if not caption_url:
            return {"error": "Caption URL not found"}, 404

        # Fetch the transcript XML
        transcript_response = requests.get(caption_url)
        if transcript_response.status_code != 200:
            return {"error": "Failed to fetch transcript"}, 400

        # Parse the transcript XML
        transcript_soup = BeautifulSoup(transcript_response.text, "html.parser")
        transcript_texts = []
        for text_tag in transcript_soup.find_all("text"):
            transcript_texts.append({
                "text": text_tag.text,
                "start": float(text_tag.get("start")),
                "duration": float(text_tag.get("dur", 0))
            })

        # Convert to DataFrame (if needed for further processing)
        df = pd.DataFrame(transcript_texts)
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": f"Error extracting YouTube transcript: {str(e)}"}, 500


@app.route('/transcript', methods=['GET'])
def get_transcript():
    logging.info("Request received at /transcript")
    video_id = request.args.get('video_id')
    if not video_id:
        return jsonify({"error": "video_id is required"}), 400

    try:
        logging.info(f"Fetching transcript for video ID: {video_id}")
        transcript = extract_youtube_transcript(video_id)
        if isinstance(transcript, tuple):  # Handle errors returned as a tuple
            logging.info(f"Error occurred: {transcript[0]}")
            return jsonify(transcript[0]), transcript[1]
        return jsonify(transcript), 200
    except Exception as e:
        logging.error(f"Exception occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Handle dynamic port assignment for Render
    import os #Ensure os is imported
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
