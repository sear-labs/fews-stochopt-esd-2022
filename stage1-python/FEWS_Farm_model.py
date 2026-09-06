# -*- coding: utf-8 -*-
"""
Initial Scenario for FEW Model
Choose between utility water and an alternate water technology
Choose between utility energy and an alternate energy technology
Choose between 2 different crops
All variables dependant on water
Water informs the yields for the crops
Water informs how much energy is needed
"""

from pyomo.environ import *
import pandas as pd 

# create a model
model = ConcreteModel()

# declare decision variables
#Utility Water
model.uw = Var(domain=NonNegativeReals)
#Utility Energy
model.ue = Var(domain=NonNegativeReals)

#Alternative Water
model.aw = Var(domain=NonNegativeReals)
#Alternative Energy
model.ae = Var(domain=NonNegativeReals)
#Total Water
model.tw = Var(domain=NonNegativeReals)
#Total Energy
model.te = Var(domain=NonNegativeReals)
#Yield Crop 1
model.yc1 = Var(domain=NonNegativeReals)
#Yield Crop 2
model.yc2 = Var(domain=NonNegativeReals)
#Binary Decision to Plant Crop 1
model.bcc1 = Var(domain=Binary)
#Binary Decision to Plant Crop 2
model.bcc2 = Var(domain=Binary)
#Investment Decsion in Alternative Energy
model.iae = Var(domain=Binary)
#Investment Decision in Alternative Water
model.iaw = Var(domain=Binary)

#parameters
#Precipatation
p = 0.254
#Price of Crop 1
pc1 = 200
#Price of Crop 2
pc2 = 250
#Price of Utility Water
puw = 1
#Price of Utility Electricity
pue = 0.12
#Unit Cost of Alternative Electricity
pae = 0
#Unit Cost of Alternative Water
paw = 2
#Capital Cost of Alternative Energy
ccae = 1000
#Capital Cost of Alternative Water
ccaw = 1000
#Big M
MM = 999999
#Area
A = 1


# declare objective
model.profit = Objective(
    expr = (model.yc1*pc1 + model.yc2*pc2 - puw*model.uw - pue*model.ue - paw*model.aw - pae*model.ae
            - ccae*model.iae - ccaw*model.iaw)*A,
    sense = maximize)

# declare constraints
#Total water is sum of all water sources including precipitation
model.waterbalance = Constraint(expr = model.uw + model.aw + p == model.tw)
#Total Energy is sum of all energy sources
model.energybalance = Constraint(expr = model.ue + model.ae == model.te)
#Need 0.383 kWh / m^3 of water
model.waterenergyconv = Constraint(expr = 0.383*(model.uw + model.aw) == model.te)
#Yield Function for Crop 1
model.yieldcrop1 = Constraint(expr = -21.84*model.tw**2 + 32.9*model.tw - 5.8556 >= model.yc1)
#Yield Function for Crop 2, made up function inspired by the first yield function
model.yieldcrop2 = Constraint(expr = -30*model.tw**2 + 40*model.tw - 5 >= model.yc2)
#Cannot use alternative energy unless it is invested in
model.invae = Constraint(expr = model.ae <= MM*model.iae)
#Cannot use alternative water unless it is invested in
model.invaw = Constraint(expr = model.aw <= MM*model.iaw)
#Cannot harvest crop 1 unless it is planted
model.invc1 = Constraint(expr = model.yc1 <= MM*model.bcc1)
#Cannot harvest crop 2 unless it is planted
model.invc2 = Constraint(expr = model.yc2 <= MM*model.bcc2)
#Can only choose to plant one crop
model.cc = Constraint(expr = model.bcc1 + model.bcc2 <= 1)
#Constraint on Utility Water (10, 0.3, 10, 0.005,0.005)
model.limitedwater = Constraint(expr = model.uw <= 0.005)
#Constraint on Utility Electricity (10, 0.1, 0.005,10,0.005)
model.limitedelectricity = Constraint(expr = model.ue <= 0.005)


# solve
SolverFactory('gurobi').solve(model).write()

#Solutions of interest

print("Profit = ", model.profit(), "$")
print("Yield C1 = ", model.yc1(), " tonnes of crop 1 / acre")
print("Yield C2 = ", model.yc2(), " tonnes of crop 2 / acre")
print("Utility Water Used = ", model.uw(), " m^3/acre utility water")
print("Alternate Water Used = ", model.aw(), " m^3/acre alternate water")
print("Utility Energy Used = ", model.ue(), " kWh/acre utility energy")
print("Alternate Energy Used = ", model.ae(), " kWh/acre alternate energy")



# add the following to your python script
DF = pd.DataFrame()
for v in model.component_objects(Var,active=True):
    for index in v:
       DF.at[index, v.name] = value(v[index])
       
       
# New Readable Database

      
       
       
       
