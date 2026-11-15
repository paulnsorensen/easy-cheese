# Generalization in Adaptive Data Analysis and Holdout Reuse

Cynthia Dwork, Vitaly Feldman, Moritz Hardt, Toniann Pitassi, Omer Reingold, and Aaron Roth's peer-reviewed paper (NIPS 2015), last verified 2026-10-17, supports the claim that reusing a holdout set adaptively can overfit the holdout itself.
Canonical source: [Generalization in Adaptive Data Analysis and Holdout Reuse](https://papers.nips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html)

## Adaptive holdout overfitting

The holdout reuse paper notes that in practice "new analyses and hypotheses are proposed after seeing the results of previous ones" (source L8). It warns that "reusing a holdout set adaptively multiple times can easily lead to overfitting to the holdout set itself" (L9).

## How easy-cheese research applies it

An optimization loop that consults the same reserved tasks on every iteration turns those tasks into development evidence. Keep a separate reserve for the final validation, and do not tune against it.

## Limits of the holdout evidence

The paper works in a formal statistical setting. It supports caution in agent evaluation design. It does not give a sample size for agent tasks.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://papers.nips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html · Updated: 2026-10-18_
