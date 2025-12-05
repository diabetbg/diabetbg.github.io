import os
from typing import Any

import inotify.adapters
import trio

import genweb as w
from conf import initer
from md2html import Page, md2html

parent = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
blogPath = os.path.join(parent, "content")
generatedBlogPath = os.path.join(parent, "static")


handle = {"IN_CREATE", "IN_DELETE", "IN_MOVED_FROM", "IN_MOVED_TO", "IN_CLOSE_WRITE"}

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
        w.div({"class": '"bg"', "id": '"bg1"'}, [w.Content(" ")]),
        w.div({"class": '"bg"', "id": '"bg2"'}, [w.Content(" ")]),
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


def inotifyLoop():
    i = inotify.adapters.Inotify()

    i.add_watch(blogPath)

    for event in i.event_gen(yield_nones=False):
        (_, types, path, filename) = event

        # print(f"PATH=[{path}] FILENAME=[{filename}] EVENT_TYPES={types}")
        for etype in types:
            if etype in handle:
                place = os.path.join(path, filename)
                path = place[len(parent) :]
                if etype not in {"IN_DELETE", "IN_MOVED_TO"}:

                    async def wrapper():
                        return await makePost(place, force=True)

                    trio.from_thread.run(wrapper)


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


@initer
async def trav(origin=blogPath):
    for file in os.listdir(origin):
        fpath = os.path.join(origin, file)

        attrs = await getAttrs(fpath)
        id = attrs.get("id")
        pos = attrs.get("pos")

        if id is None or pos is None:
            continue

        outPath = os.path.basename(file)[:-3] + ".html"

        setNth(top, int(pos), (id, outPath))

    while None in top:
        top.remove(None)

    for file in sorted(os.listdir(origin)):
        fpath = os.path.join(origin, file)
        fpath = await makePost(fpath)

    await trio.to_thread.run_sync(inotifyLoop)
