# TODO: Replace BERT models with Groq API

- [ ] Add `groq` to `backend/requirements.txt`
- [ ] Update imports in `backend/main.py`: Remove `transformers`, add `groq` and `os`
- [ ] Remove BERT model loading and global variables in `backend/main.py`
- [ ] Modify `detect_abusive` function to use Groq API for toxicity classification
- [ ] Keep regex fallback in `detect_abusive`
- [ ] Set `GROQ_API_KEY` environment variable
- [ ] Install updated dependencies
- [ ] Test moderation endpoint
