# postgre_operations/utils/remove_usfm_markers.py

import re
import logging

# Configure module-level logging
logger = logging.getLogger(__name__)

def remove_usfm_markers(text):
    """
    Remove USFM markers from the verse text while preserving content within certain markers.
    
    - Removes markers like \\f...\\f*, \\x...\\x*, \\fig...\\fig* entirely.
    - For \\w...\\w* and \\+w...\\+w*, keeps text before '|' (removes Strong's numbers).
    - For formatting markers like \\it...\\it*, preserves the text inside.
    - Removes verse markers (\\v) and their numbers.
    
    Args:
        text (str): The input text containing USFM markers.
    
    Returns:
        str: The cleaned text with USFM markers removed or processed.
    
    Raises:
        re.error: If a regex pattern is invalid (returns original text with error logged).
    """
    logger.debug("Starting USFM marker removal")
    try:
        def clean_content(content, marker):
            """Helper to clean content within specific markers."""
            if marker in ['w', '+w']:
                parts = content.split('|', 1)
                return parts[0].strip() if parts else ''
            return content

        # Step 1: Remove verse marker (\v) and its number
        text = re.sub(r'\\v\s+\d+\s*', '', text, flags=re.DOTALL)

        # Step 2: Handle self-closing markers with content (e.g., \w...\w*, \f...\f*)
        pattern = r'\\(\+?\w+)(.*?)\\(\1)\*'
        while re.search(pattern, text, flags=re.DOTALL):
            text = re.sub(
                pattern,
                lambda m: clean_content(m.group(2), m.group(1)) if m.group(1) in ['w', '+w'] else '' if m.group(1) in ['f', 'x', 'fig'] else m.group(2),
                text,
                flags=re.DOTALL
            )

        # Step 3: Handle formatting markers (e.g., \it...\it*) by keeping the text inside
        formatting_markers = ['it', 'bd', 'sc']
        for marker in formatting_markers:
            pattern = rf'\\{marker}(.*?)\\{marker}\*'
            text = re.sub(pattern, r'\1', text, flags=re.DOTALL)

        # Step 4: Remove any remaining standalone markers (e.g., \it, \it*)
        pattern_simple = r'\\(\+?\w+)\*?'
        text = re.sub(pattern_simple, '', text, flags=re.DOTALL)

        # Step 5: Normalize whitespace
        text = ' '.join(text.split())

        logger.debug("Completed USFM marker removal")
        return text.strip()
    except re.error as e:
        logger.error(f"Regex error in remove_usfm_markers: {str(e)}")
        return text  # Return original text if regex fails

if __name__ == "__main__":
    # Example usage for testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    sample_text = r"\v 4 \it \+w In|strong=\"G1722\"\+w* test\it*"
    print(remove_usfm_markers(sample_text))