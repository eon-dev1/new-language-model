## Preview project data 

db.bible_texts.find({ language_code: "bughotu" })

## Delete Project Data
// Connect to the right database
use nlm_db

// Delete from all collections (run each line)
db.bible_texts.deleteMany({ language_code: "bughotu" })
db.bible_books.deleteMany({ language_code: "bughotu" })
db.languages.deleteMany({ language_code: "bughotu" })
db.dictionaries.deleteMany({ language_code: "bughotu" })
db.grammar_systems.deleteMany({ language_code: "bughotu" })

Or as a one-liner:
mongosh --port 27018 --eval 'use nlm_db; ["bible_texts","bible_books","languages","dictionaries","grammar_systems"].forEach(c => print(c + ": " + db[c].deleteMany({language_code:"bughotu"}).deletedCount + " deleted"))'