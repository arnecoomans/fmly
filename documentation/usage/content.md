# Photos & documents

"Photos & documents" holds everything uploaded to the archive: photos, documents like letters and civil records, newspaper clippings, books, objects and recordings. Each item has a page with the image, what's known about it, and who's on it.

## Adding content

For editors: *More* → **Add content**, or drop files on the dashboard. Several files at once is fine - they're uploaded one by one, in name order. On a person's page in edit mode, the dropzone in *Content* adds files already linked to that person ([People](people.md)).

- A file that's **already in the archive** is recognised and not added twice.
- Each upload becomes a **draft** in your **inbox**: visible only to you until you publish it.

## The inbox

Your drafts, in the order they were scanned or taken. Open one to describe it; **next in inbox** takes you to the next.

**Make these one item:** select several drafts - the pages of a letter, the front and back of a photo - and they become one item with pages. The first selected is the whole, the others its pages, in order.

On an item with pages - the whole and each of its pages alike - the arrows on the image browse through all of them in place, starting at the one you're on; full-screen too. A page's thumbnail under *Parts* opens that page itself - its own details, people and transcript.

## Describing an item

In edit mode, on the item's page:

- **Name**, **description** and **date** - a date can be exact, *ca.*, *before* or *after*, or just a year. For a book, the date is when it was published.
- **Kind** - photo, document, book, object, recording. A photo is *portrait* or *group* (posed), *candid* (not posed), or *historical*; hover over a button for its meaning.
- **People** on it - each with how, if you know: *subject* (it's about them - their record, their request), *creator* (wrote or made it - a photographer too), *addressee*, *depicted* (in it) or *possibly depicted* (you think so - an identification to confirm), or *owner* (it was theirs). In that order of weight: where several fit - a passport request with his photo - choose the first that does (subject). The item's kind **suggests** one, marked in the menu - a portrait: subject; a candid or group photo: depicted; an identity document or civil record: subject - but never sets it; in edit mode a menu next to each person. Without a role they're simply linked. A book's authors have their own field. **Tags**, **places**, and the **events** it documents.
  A tag has a page of its own with everything that carries it; in edit mode its name, description and the tag it sits under can be changed there. Links to the old name keep working.
- **Source** - where it came from: a person, an archive, a web address.
- **Thumbnail** - choose the part of the image shown in lists.
- **Use as portrait of ...** - make this photo someone's avatar.

When it's complete, **publish** it - it leaves your inbox and is shared.

## Viewing

Click the image to open it full screen: **scroll** to move around, **pinch** (or Ctrl + scroll) to zoom - a sharper version loads as you zoom in. ‹ and › step through the pages. *Open original* shows the file itself.

A **PDF** opens in the browser's own viewer. In lists and on the dashboard it shows its first page as a thumbnail - made by the archive itself, nothing to add by hand; *Thumbnail* in edit mode chooses the part of that page shown, as for a photo.

## Favorites

Found something you really like? The **heart** on its page makes it one of your favorites; click it again to undo. Favorites are shared: the item shows how many people favorited it and who.

- **Your favorites** - *More* → **Your favorites**: everything you favorited, the most recent first.
- **Most favorited** - in a list of photos and documents, the ♥ sort puts what the family likes most on top. Cards show a heart with the count.
- Only a published item can be a favorite.

## Transcribing

A transcript makes a document readable and searchable. **Transcribe** opens the image beside the text:

- Type what's written, or let **OCR** read the image first, then correct it.
- Use a **?** where you can't read something.
- Mark a transcript **incomplete** until it's done; translations sit next to the original.

Transcripts still to do or to check are listed under loose ends on the dashboard.


**As written.** A transcript is shown exactly as typed - every character, the line breaks of the original. A little Markdown helps without changing anything: `## ` before a line makes it a heading (a newspaper's headline), `**bold**` and `*italic*` copy what the original stresses - a ship's name, a heading in a list - a table can lay out a register, and a mention - `[the words in the text](person:…)` - links a name in it to that person. The asterisks must hug their words: an asterisk after a word, as a footnote mark (`echtg.*;`), stays an asterisk; `\*` is one too. Lists and other markup are left as typed: a numbered line in a register stays numbered as in the original. Text from OCR or Delpher is never Markdown: where it would become a heading or bold (`# 12`, `*Batavia*`), it arrives with a backslash (`\# 12`, `\*Batavia\*`) so it stays as read - take the backslash away if the original really has it.

**Mentioning who's in it.** Select the words that name someone - "Corry Bake" - and click **@ mention** above the text (or press Alt+M): the words stay exactly as written, and the list shows who they might be; choose, and the name links to that person. A bare `@` does nothing here - in a transcript only the document's own words name someone. The person's page then lists the item under *mentioned in*.