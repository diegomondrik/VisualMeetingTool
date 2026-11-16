# WI-2.0.0: why the commits this evidence names are not on GitHub

2026-11-16. The independent review found that earlier versions of the proposal, the test data and this
evidence quoted the real meeting used as the regression case. The repository is public, so the owner asked
that nothing of that meeting be visible ("si alguien mas lo puede ver cambialo") and chose a clean history.

The work item's 22 commits were replaced by four, from `main`, with the cleaned documents: the proposal,
the contract and plan, the code, and this evidence. The tree of the last of the four is identical to the
tree of the last of the 22. The 22 are kept only on the owner's computer, in the local branch
`backup/2.0.0-historia-completa`, which is never pushed.

So the commits that the files of this folder name (d80a8d0, 8f46737, 886b5e4, 4d65584, 19fcf8f, 8ca68fd,
841fe80) exist only in that local branch. The full suite was run again on the clean history: see
local-test-run.txt for the commit it ran on.
