// This is based on the example /usr/share/doc/root/tutorials/tree/copytree.C included in the root installation
void copytree() {
  const auto filename = "test.root";
  const auto treename = "data";
  TFile oldfile(filename);
  TTree* oldtree;
  oldfile.GetObject(treename, oldtree);

  // Deactivate all branches
  oldtree->SetBranchStatus("*", 0);

  // Activate only branches needed
  for(auto activeBranchName : {"timeStamp", "Conversion.arrivalTime"}) oldtree->SetBranchStatus(activeBranchName, 1);

  // Create a new file + a clone of old tree in new file
  TFile newfile("small.root", "recreate");
  auto newtree = oldtree->CloneTree();

  newtree->Print();
  newfile.Write();
}
