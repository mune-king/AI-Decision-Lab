# vdtNext ZIP uploader

Students scan the QR code, open the page, fill in the form and upload one ZIP file (about 10MB). There is no GitHub operation, account or program download for students. This directory is independent of AI Decision Lab; nothing outside `vdtnext/` is changed.

## Structure

- `index.html`: student page (static, no build). It is published by Vercel with Root Directory set to `vdtnext`.
- `setup.sql`: run once in the Supabase SQL Editor (project `plirzczxdhddfcxldnxj`).
- Storage `vdtnext-pilot`: **private** bucket, ZIP only, max 30MB. Anonymous users can only create `submissions/<uuid>.zip`; they cannot list, download, overwrite or delete.
- `public.vdtnext_uploads`: research data (research ID, age, measurement date, font-size order, research consent, file size, SHA-256, storage path). There is no student number and no original file name. RLS on, no policies, so the Data API cannot read it.
- `vdtnext_private.course_submissions`: student number + `upload_id`, the course-submission record. It is in a schema not exposed through the API. The `upload_id` link makes this a correspondence table, so only the instructor should hold it.
- `vdtnext_register_upload` RPC: registers metadata only after the ZIP exists in Storage, and returns a receipt number and the stored byte count.

## Consent is separate from the course submission

Submission is accepted whether the student chooses agree or disagree, and the page says the choice does not affect grades. For analysis, use only `research_consent = 'agree'`. The consent value is not in the course table, so grading does not need to see it. The formal explanation document and any ethics procedure are separate from this page.

## Instructor operations (Supabase dashboard)

- ZIP files: Storage → `vdtnext-pilot` → `submissions/` (file name = `<upload id>.zip`).
- Research export: `select * from public.vdtnext_uploads where research_consent = 'agree' and research_id not like 'TEST%' order by submitted_at;`
- Submission check: `select student_number, submitted_at, upper(left(upload_id::text, 8)) as receipt from vdtnext_private.course_submissions order by student_number;`
- Remove test rows: `delete from public.vdtnext_uploads where research_id like 'TEST%';`, then delete the matching objects in Storage.

## Tests and materials

- `node vdtnext/test-upload.cjs`: offline test of validation, ZIP signature, upload, registration, and a retry that does not upload twice.
- `python3 vdtnext/tools/make_dummy_zip.py dummy.zip`, then `node vdtnext/tools/e2e-check.mjs dummy.zip`: real upload, plus checks that anonymous users cannot read it back.
- `python3 vdtnext/tools/make_poster.py <URL> <outdir>`: QR (SVG/PNG) and the A4 poster PDF.

Limits: anyone with the URL can submit, and fabricated or spam submissions are possible. This is a lecture pilot, not identity verification. Uploaded objects that were never registered (abandoned attempts) can be found by comparing Storage with `vdtnext_uploads.storage_path`.
