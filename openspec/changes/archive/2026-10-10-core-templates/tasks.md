## 1. Loading

- [x] 1.1 xfail tests for "Templates are validated when they load"
- [x] 1.2 Implement the YAML tags, the template models and `Templates.load`; remove the markers

## 2. Message rendering

- [x] 2.1 xfail tests for "Message text is rendered with placeholders", "URL fields need an http
      result", "Empty embeds are dropped" and "Colors and timestamps follow v3"
- [x] 2.2 Implement content and embed rendering; remove the markers
- [x] 2.3 xfail tests for "Components keep their rows" and "Model keys insert runtime objects"
- [x] 2.4 Implement components and models; remove the markers

## 3. Modals

- [x] 3.1 xfail tests for "Modal templates render text inputs"
- [x] 3.2 Implement `render_modal`; remove the markers

## 4. Close

- [x] 4.1 Update `docs/porting-guide.md`
- [x] 4.2 Gate passes, push, CI green
- [x] 4.3 Archive the change and run `openspec validate --all --strict`
