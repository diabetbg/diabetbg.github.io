import os
from typing import Any

import trio

import genweb as w
from md2html import Page, md2html

curdir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
blogPath = os.path.join(curdir, "content")
generatedBlogPath = os.path.join(curdir, "static")


top: list[tuple[str, str]] = []


def setNth(l: list, n: int, item: Any):
    l.extend([None] * (n - len(l) + 1))
    l[n] = item


def transform(p: Page):
    active = p.attrs.get("id")

    p.body.children = [
        w.div(
            {"class": '"topnav"'},
            [
                w.p({}, [w.Content(active or "")]),
            ],
        ),
        w.inp({"type": '"checkbox"', "id": '"expand-toggle"'}),
        w.span(
            {"class": '"triangle"'}, [w.Content(" ")]
        ),  # this is just a hack because a self-closing span doesnt work
        w.div(
            {"class": '"sidenav"'},
            [
                w.a(
                    {
                        "href": f'"{link}"',
                        **({"class": '"active"'} if active == name else {}),
                    },
                    [w.Content(name)],
                )
                for (name, link) in top
            ],
        ),
        w.div({"class": '"content"'}, p.body.children),
    ]


async def makePost(path, force=False):
    outPath = os.path.join(generatedBlogPath, os.path.basename(path))[:-3] + ".html"
    async with await trio.open_file(path, "r") as f:
        out = md2html(await f.read())
        transform(out)
    if not force and os.path.exists(outPath):
        return outPath
    async with await trio.open_file(outPath, "w+") as f:
        await f.write(out.generate())
    return outPath


async def getAttrs(fpath):
    # this is jank
    out: dict[str, str] = {}
    f = await trio.open_file(fpath)
    for l in await f.readlines():
        if l.startswith("-attr:"):
            l = l.removeprefix("-attr:").strip()
            field, val = (a.strip(" ") for a in l.split("="))
            out[field] = val
    await f.aclose()

    return out


async def trav(origin=blogPath):
    for file in os.listdir(origin):
        fpath = os.path.join(origin, file)

        attrs = await getAttrs(fpath)
        id = attrs.get("id")
        pos = attrs.get("pos")

        if id is None or pos is None:
            continue

        outPath = os.path.join(os.path.basename(file))[:-3] + ".html"

        setNth(top, int(pos), (id, outPath))

    while None in top:
        top.remove(None)

    for file in sorted(os.listdir(origin)):
        print(f"generated {file}")
        fpath = os.path.join(origin, file)
        fpath = await makePost(fpath, force=True)


trio.run(trav)
