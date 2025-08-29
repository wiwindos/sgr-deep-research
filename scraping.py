"""
Web scraping and YouTube transcript fetching utilities
"""
import re
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import trafilatura


def extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL, return None if not YouTube"""
    youtube_patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|m\.youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
    ]

    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)  # Return video ID

    return None  # Not a YouTube URL

def fetch_youtube_transcript(url: str) -> dict:
    """Fetch YouTube transcript by video ID"""
    try:
        video_id = extract_youtube_id(url)
        if not video_id:
            return {'url': url, 'status': 'error', 'error': 'Invalid YouTube URL'}

        transcript_list = YouTubeTranscriptApi().list(video_id)
        original_transcript = None
        first_transcript = next(iter(transcript_list), None)
        if first_transcript is None:
            return {'url': url, 'status': 'error', 'error': 'No transcript found'}

        for transcript in transcript_list:
            if not transcript.is_generated:
                original_transcript = transcript
                break
        if not original_transcript:
            original_transcript = transcript_list.find_transcript([first_transcript.language_code])

        transcript_data = original_transcript.fetch()
        formatter = TextFormatter()
        transcript_text = formatter.format_transcript(transcript_data)

        if transcript_text and len(transcript_text.strip()) > 100:  # Ensure meaningful content
            return {
                'url': url,
                'full_content': transcript_text.strip(),
                'status': 'success',
                'char_count': len(transcript_text)
            }

        return {'url': url, 'status': 'empty', 'error': 'No meaningful transcript found'}

    except Exception as e:
        return {
            'url': url,
            'status': 'error',
            'error': f"YouTube transcript: {str(e)[:200]}"
        }

def fetch_page_content(url: str) -> dict:
    """Fetch content using appropriate method (YouTube transcript or web scraping)"""

    video_id = extract_youtube_id(url)
    if video_id:
        # YouTube video - get transcript
        return fetch_youtube_transcript(url)

    # Regular websites - use trafilatura
    try:
        # Fetch with trafilatura defaults
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            # Extract with Markdown formatting and readability algorithm
            content = trafilatura.extract(
                downloaded,
                output_format='markdown',
                favor_precision=True,
                include_tables=True,
                include_links=False,
                include_images=False,
                deduplicate=True,
                target_language=None   # Auto-detect language
            )
            if content and len(content.strip()) > 100:  # Ensure meaningful content
                return {
                    'url': url,
                    'full_content': content.strip(),
                    'status': 'success',
                    'char_count': len(content)
                }

        return {'url': url, 'status': 'empty', 'error': 'No meaningful content extracted'}

    except Exception as e:
        return {
            'url': url,
            'status': 'error',
            'error': str(e)[:200]  # Limit error message length
        }
