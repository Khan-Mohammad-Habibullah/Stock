Holdings files land here: the board's "Update holdings" button (My holdings tab)
saves one, or Claude writes one from a Nordnet export sent in chat. Each file
holds only each holding's name, quantity and value in SEK, read from a Nordnet
"Innehav" export; the export itself is never stored. The "Update stock board"
workflow applies the file to data/portfolio.json, rebuilds the board and
removes the file.
