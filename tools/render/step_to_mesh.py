#!/usr/bin/env python3
"""STEP (com cores) → GLB (three.js / visualizadores web) + STL (visualizador 3D do GitHub).

Usa OpenCascade via OCP:  pip install cadquery-ocp
Uso: python3 step_to_mesh.py placa.step saida.glb saida.stl
"""
import sys

from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.Message import Message_ProgressRange
from OCP.RWGltf import RWGltf_CafWriter
from OCP.RWMesh import RWMesh_CoordinateSystem
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.StlAPI import StlAPI_Writer
from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
from OCP.OCP.collections import IndexedDataMap_TCollection_AsciiString_TCollection_AsciiString as InfoMap
from OCP.OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.TopoDS import TopoDS_Compound
from OCP.BRep import BRep_Builder
from OCP.XCAFDoc import XCAFDoc_DocumentTool


def main(step, glb, stl):
    doc = TDocStd_Document(TCollection_ExtendedString("pfc"))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    if reader.ReadFile(step) != IFSelect_RetDone:
        raise SystemExit("falha ao ler STEP")
    reader.Transfer(doc)
    tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    labels = TDF_LabelSequence()
    tool.GetFreeShapes(labels)
    comp = TopoDS_Compound()
    bld = BRep_Builder()
    bld.MakeCompound(comp)
    for i in range(1, labels.Length() + 1):
        shp = tool.GetShape_s(labels.Value(i))
        BRepMesh_IncrementalMesh(shp, 0.02, False, 0.25, True)
        bld.Add(comp, shp)
    w = RWGltf_CafWriter(TCollection_AsciiString(glb), True)
    # STEP do KiCad: mm, Z para cima  →  GLB em mm, Y para cima (convenção glTF/three.js)
    conv = w.ChangeCoordinateSystemConverter()
    conv.SetInputLengthUnit(0.001)
    conv.SetInputCoordinateSystem(RWMesh_CoordinateSystem.RWMesh_CoordinateSystem_Zup)
    conv.SetOutputLengthUnit(0.001)
    conv.SetOutputCoordinateSystem(RWMesh_CoordinateSystem.RWMesh_CoordinateSystem_glTF)
    w.Perform(doc, InfoMap(), Message_ProgressRange())
    sw = StlAPI_Writer()
    sw.ASCIIMode = False
    sw.Write(comp, stl)
    print("✓", glb, "+", stl)


if __name__ == "__main__":
    main(*sys.argv[1:4])
