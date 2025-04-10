#!/bin/python
import ROOT
import numpy as np
import sys
from tqdm import tqdm


filepath = "test.root"
ntupleInFile = "data"
f = ROOT.TFile.Open(filepath,'READ')
tree = f.Get(ntupleInFile)
listofleaves = tree.GetListOfLeaves()
# print(listofleaves)

leafNames = []
mydict = {}
data = {}
for atree in listofleaves:
  leafNames.append(atree.GetName())
  if atree.GetTypeName() == "TArrayF":
    mydict[atree.GetName()] = [[],atree.GetTypeName()]
    data[atree.GetName()] = ROOT.TArrayF()
    tree.SetBranchAddress(atree.GetName(),data[atree.GetName()])
  else:
    mydict[atree.GetName()] = [[],atree.GetTypeName()]

for i in tqdm(range(tree.GetEntries())):
  tree.GetEntry(i)
  for branch in mydict:
    if mydict[branch][1] == "TArrayF":
      mydict[branch][0].append(np.asarray(data[branch]))
    else:
      mydict[branch][0].append(tree.GetLeaf(branch).GetValue())

np.savez_compressed("data.npz", mydict)

npzFile = np.load("data.npz", allow_pickle=True)
data = npzFile["arr_0"]
#data.item().get("branchName")