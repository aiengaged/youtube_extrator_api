from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import re
import json

app = Flask(__name__)

def extract_youtube_transcript(video_id):
    """
    Extracts the transcript of a YouTube video using its video ID.

    Args:
        video_id (str): The ID of the YouTube video.

    Returns:
        list: A list of dictionaries containing the transcript text, start time, and duration.
    """
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
        if not captions:
            return {"error": "No captions found"}, 404

        # Fetch the transcript from the first available caption track
        caption_url = captions[0].get("baseUrl")
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

        return transcript_texts
    except Exception as e:
        return {"error": f"Error extracting YouTube transcript: {str(e)}"}, 500

@app.route('/transcript', methods=['GET'])
def get_transcript():
    """
    Endpoint to fetch YouTube video transcripts.

    Query Parameters:
        video_id (str): The ID of the YouTube video.

    Returns:
        JSON response containing the transcript or an error message.
    """
    video_id = request.args.get('video_id')
    if not video_id:
        return jsonify({"error": "video_id is required"}), 400

    try:
        transcript = extract_youtube_transcript(video_id)
        if isinstance(transcript, tuple):  # Handle error from function
            return jsonify(transcript[0]), transcript[1]
        return jsonify(transcript), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
