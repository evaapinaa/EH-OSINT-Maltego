# EH-OSINT-Maltego

This project contains two custom Maltego transforms developed in Python using the `maltego-trx` library. Both transforms take an email address as input and gather information from external sources, specifically the University of Murcia directory and ProxyNova's dataset of leaked passwords.

## UMDirectory

The [University of Murcia directory](https://www.um.es/web/directorio/) is a public directory that provides contact and professional information about university staff, including their departments, positions and contact details.

This transform automates searches in the directory using an email address as input. However, it only accepts `@um.es` addresses. Then, it creates Maltego entities with the available information, such as names, phone numbers, departments, offices, and institutional roles.

The transform works as follows. First, `query_api()` sends a POST request to the UM directory API. Since the API may return several results, `exact_matches()` filters them to keep only those matching the input email address. Then, `collect()` extracts the available information and prepares the corresponding Maltego entities, which are added to the graph by `create_entities()`. This last function also validates the email address and avoids adding duplicate entities.

Furthermore, it supports people with multiple positions within the university, such as a professor who is also the Rector or a Dean. To handle these cases, `collect()` goes through all the relations returned by the API. It checks the `filiaciones_desc` field to identify the type of affiliation and, when its value is `Cargo`, retrieves the specific institutional role from `cargos_desc`. Otherwise, it keeps the corresponding affiliation, such as `PDI`. This allows the transform to distinguish between academic positions, affiliations and institutional roles, even when they belong to the same person.

It is worth mentioning that the transform uses a session identifier, stored in `session_id.txt`, which is included in the API request when available. This value depends on your specific session, so don’t forget to update it if it expires!

## ProxyNovaExposure

[ProxyNova](https://www.proxynova.com/tools/comb) is an online tool for searching through collections of leaked email addresses and passwords, which can be useful for identifying possible credential exposure.

This transform uses the ProxyNova API to check whether an email address appears in these records.

The **`check_exposure()`** function sends a GET request to the API and checks whether any returned entry contains the exact email address. Finally, the **`create_entities()`** function adds a Phrase entity to the Maltego graph indicating whether password exposure was detected. The password itself is not displayed, but you can check it on the website.

## Test from Windows without Maltego

To check that the transforms return the expected result before creating the graphs in Maltego, you can run the following test on a Windows operating system using [Python 3.8+](https://www.python.org/downloads/).

Firstly, install the necessary dependencies and set up the virtual environment.

```
cd C:\umu_transform
python3 -m venv venv
venv\Scripts\activate
python3 -m pip install -r requirements.txt
```

Secondly and finally, test each transform without using Maltego, passing the email address as the last argument. For the first run, don’t forget to include a valid session ID.

```
python3 project.py local umdirectory arm@um.es
python3 project.py local proxynovaexposure felixgm@um.es
```

## Authors

- Eva Pina Dubovtseva.
- Iván Álvarez Belotto.
