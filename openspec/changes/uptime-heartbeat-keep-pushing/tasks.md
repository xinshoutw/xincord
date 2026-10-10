## 1. Logs show only the URL's origin

- [x] 1.1 xfail tests for "Logs show only the URL's origin": `origin` and `redact` against stubs in
      `logs.py`, and the push lines that name the origin (a malformed answer through aiohttp too)
- [x] 1.2 Implement `origin` and `redact` and use them in every line that shows the URL; remove the
      markers

## 2. Pushing goes on after every failure

- [x] 2.1 xfail tests for "The status code decides what follows" and "Each listener pushes at once,
      then after a fixed delay": a 404 and every other failure keep the loop going, the 404 and 521
      lines name the origin, independent listeners
- [x] 2.2 Let `Pusher.run` push until it is cancelled, log the 404 and 521 lines with the origin
      and update the bundled `config.yaml` comment; remove the markers

## 3. Failures logged when they start, change or end

- [x] 3.1 xfail tests for "A failure is logged when it starts, changes or ends" and "The URL carries
      the REST ping": `Failures` against a stub in `logs.py`, repeated pushes and pings
- [x] 3.2 Implement `Failures` and use it for the pushes and the pings; remove the markers

## 4. Checks and docs

- [ ] 4.1 Run the plugin's pushes against real aiohttp errors (a malformed answer, a connect
      timeout, a refused connection) in a scratch probe and check that no line holds the token
- [ ] 4.2 Porting guide: differences rows, the aiohttp pitfall and the loop convention; port-plugin
      skill notes
- [ ] 4.3 Audit: every scenario of the delta has a test

## 5. Close

- [ ] 5.1 Gate passes, push, CI green
- [ ] 5.2 Archive the change and run `openspec validate --all --strict`
- [ ] 5.3 Update `HANDOFF.md` and `docs/porting/owner-review.md`; push; CI green
