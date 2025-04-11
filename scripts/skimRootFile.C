// This is based on the example /usr/share/doc/root/tutorials/tree/copytree.C included in the root installation
// This script can be executed like root -b -q -l 'skimRootFile.C("data.root")' and will create `data_small.root` from `data.root`
void skimRootFile(const char* input) {
  const auto filename = input;
  const auto treename = "data";
  TFile oldfile(filename);
  TTree* oldtree;
  oldfile.GetObject(treename, oldtree);

  std::vector<std::string> activeBranches = {"timeStamp", "Conversion.arrivalTime"};
  // Deactivate branches not used
  //\Remark: Do not deactivate all branches and reactivate only the branches of interest - this will not work for the TimeStamp!
  auto branchList = oldtree->GetListOfBranches();
  for(size_t i = 0; i < branchList->GetSize(); i++) {
    auto it = std::find(activeBranches.begin(), activeBranches.end(), branchList->At(i)->GetName());
    if(it == activeBranches.end()) {
      oldtree->SetBranchStatus(branchList->At(i)->GetName(), 0);
    }
  }

  // Create a new file + a clone of old tree in new file
  std::string out = input;
  TFile newfile((out.substr(0, out.length() - 5) + "_small.root").c_str(), "recreate");
  auto newtree = oldtree->CloneTree();

  newtree->Print();
  newfile.Write();
}
