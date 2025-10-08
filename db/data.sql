BEGIN;
INSERT INTO articles (
        document_id,
        canonical_url,
        subtype,
        created_date,
        display_date,
        first_publish_date,
        publish_date,
        last_updated_date,
        headline,
        subheadline,
        description,
        label,
        content_elements,
        promo_items,
        credits,
        taxonomy,
        raw,
        text_hash
    )
VALUES (
        'UT72IMCRGZFEPGOCSFYBCPJHGI',
        '/travel/2024/05/27/what-is-turbulence-and-why-is-it-getting-worse/',
        'standard',
        '2024-05-22T12:46:45.42Z'::timestamptz,
        '2024-05-22T12:53:16.107Z'::timestamptz,
        '2024-05-22T12:53:16.107Z'::timestamptz,
        '2025-09-28T13:04:29.668Z'::timestamptz,
        '2025-09-28T13:04:29.837Z'::timestamptz,
        'What is turbulence and why is it getting worse?',
        'A recent report found bumpier flights are on the rise',
        '',
        NULL,
        $$ { } $$::jsonb,
        NULL,
        $$ { "by": [
            {
                "_id": "katy-gillett",
                "additional_properties": {
                    "original": {
                        "firstName": "Katy",
                        "lastName": "Gillett"
                    }
                },
                "description": "Katy Gillett joined The National as assistant features editor in 2018, before becoming the weekend editor. She was a managing editor at Time Out GCC, and has edited and written for a range of publications – including Women’s Health, British GQ, Sorbet, Gulf Insider and Absolutely London.",
                "image": {
                    "auth": {
                        "1": "7366ed37c35d711c4c014ed68fbdc794f2df8c9d2ceecd6d4331d2b445b8b733"
                    },
                    "type": "image",
                    "url": "https://s3.amazonaws.com/arc-authors/thenational/4fc171d1-2cf0-4f31-ab2e-ed5dc37d2626.png"
                },
                "name": "Katy Gillett",
                "slug": "katy-gillett",
                "type": "author"
            }
        ] } $$::jsonb,
        $$ { "primary_section": { "_id": "/travel",
        "_website": "the-national",
        "description": "#febe10",
        "name": "Travel",
        "parent": { "default": "/lifestyle" },
        "parent_id": "/lifestyle",
        "path": "/travel",
        "type": "section" },
        "sections": [
            {
                "_id": "/travel",
                "_website": "the-national",
                "description": "#febe10",
                "name": "Travel",
                "parent": {
                    "default": "/lifestyle"
                },
                "parent_id": "/lifestyle",
                "type": "section"
            },
            {
                "_id": "/lifestyle",
                "_website": "the-national",
                "description": "#97d700",
                "name": "Lifestyle",
                "parent": {
                    "default": "/"
                },
                "parent_id": "/",
                "type": "section"
            }
        ],
        "tags": [
            {
                "name": "Travel",
                "slug": "travel",
                "text": "Travel",
                "type": "tag"
            }
        ] } $$::jsonb,
        $$ { } $$::jsonb,
        -- raw (full payload; we’ll store via script if you want)
        '40b95adf27a95718f69e4b878d92778b24a312c4' -- text_hash (title+dek+full body hash the script will also compute)
    ) ON CONFLICT (document_id) DO
UPDATE
SET title = EXCLUDED.title,
    dek = EXCLUDED.dek,
    description_basic = EXCLUDED.description_basic,
    last_updated_date = EXCLUDED.last_updated_date;
COMMIT;