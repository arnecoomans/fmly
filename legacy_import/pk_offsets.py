"""
Deterministic pk offsets for legacy sources that converge on the same new
model. archive.tag and archive.category both import into core.Tag, and
their old pk ranges genuinely overlap (tag: 1-36, category: 1-8) - a
straight update_or_create(pk=old_pk) would collide (e.g. tag pk=1
"verjaardag" vs category pk=1 "Photo"). Offsetting category's old pks by
a fixed amount keeps every source's rows addressable by a single formula,
so any later importer that needs to resolve an old Image.category /
Image.tag reference to a new Tag pk can do so without a lookup table.

Not used for archive.group - deliberately deferred (see import_content_tags
help text), so no offset is reserved for it yet.
"""

CATEGORY_TAG_PK_OFFSET = 1000

# archive.image, archive.attachment and archive.book all import into
# content.Content, with overlapping pk ranges (image 1-373, attachment
# 1-20, book 1-45). Images keep their pk; the others are offset.
ATTACHMENT_CONTENT_PK_OFFSET = 1000
BOOK_CONTENT_PK_OFFSET = 2000
