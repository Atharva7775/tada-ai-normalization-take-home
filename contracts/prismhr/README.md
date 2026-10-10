# PrismHR reference pack

**Available: version 2025.09 integration snapshot; not verified as the latest live API.**

`openapi/prismhr-2025.09.openapi.json` is an explicitly modified derivative of
the existing integration's `references/prism/prism_api_specs.json`. It retains
450 paths, 1,168 component schemas, formal required fields/defaults and the source
license declaration. Candidates still discover endpoint/field mappings themselves.

## Distribution basis

The source artifact's `/info/license` explicitly declares **Apache 2.0 License**
and links to [Apache's license](https://www.apache.org/licenses/LICENSE-2.0).
That artifact-specific declaration is the basis used for including this snapshot
and its derived lookup reference in the organizer's private hiring repository.
The required license copy is `LICENSE.apache-2.0.txt`; attribution and prominent
change notices appear in `NOTICE.md` and inside the derivative itself.
This does not license unrelated PrismHR website material, customer data, Tada
integration source code, or the whole hiring repository. No separate provider
permission letter or signed partner agreement was found in the searched sources.

The current upstream artifact could not be independently refreshed: the official
reference site is a JavaScript application, its page content was not retrievable
here, and the direct API-host URLs checked returned 404. This inclusion relies
on the embedded license declaration of the exact existing snapshot, not a claim
that the vendor separately approved this hiring exercise.

## Modifications and content boundary

- Removed 340 `example`/`examples` annotations.
- Omitted eight embedded JSON payload renderings from operation descriptions.
- Added derivative/provenance metadata and a prominent modification notice.
- Preserved all formal paths and component schemas, except their example annotations.
- Supplied no employee/company/payroll record fixtures or API response files.

Original SHA-256: `e1d9c05933d9bf0a8ccc416d483ec5bf4a2d41929d615daf44427c65e64b71e2`.
Distributed derivative SHA-256: `a94cbc91c482f44cade3582fd21f3f3ae51a63be26bd18bf4817325b96ca877d`.

## Lookup reference

`lookup-reference.json` contains eight intentionally partial, field-specific
domains extracted from the licensed snapshot's descriptions. Each raw code and
meaning cites a JSON Pointer in the distributed spec. These are source reference
facts, **not canonical enums or completed provider mappings**. Some lists are
descriptive examples rather than closed enums; that distinction is explicit.

Client-configured employee status/type and pay/deduction identifiers have no values
included. Do not conflate those identifiers with status classes, benefit statuses,
or the field-specific codes listed in the reference. Generate your own synthetic
lookup/response data where the contract permits open identifiers and label it synthetic.

The complete three-provider pack still requires authorized isolved and UKG Ready
materials before the seven-day clock starts. See [the audit](../../docs/REFERENCE_AUDIT.md).
