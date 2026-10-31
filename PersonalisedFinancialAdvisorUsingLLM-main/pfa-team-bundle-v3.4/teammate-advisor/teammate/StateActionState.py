from datetime import date, timedelta
from pprint import pprint
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from GoalSearch import (GoalSearch, GOAL_REACHED, GOAL_NOT_REACHABLE,
                        GOAL_NOT_YET_REACHED)
import math


class deposit(BaseModel):
    interestRate: float = Field(
        description="Yearly Interest rate of the deposit in percent")
    duration: float = Field(
        description="total duration of the deposit in years")
    compoundingDuration: float = Field(
        description="Compounding duration of the deposit in years")
    scheme_name: str = Field(description="scheme name of the deposit")
    bank_name: str = Field(
        description="bank name of the scheme name of the deposit")


class state(BaseModel):
    balance: float = Field(description="Present bank balance or the lump sum amount of the user")
    time: date = Field(description="Present time stamp.")


class OptimalActionFixedDepositToolReturnsSchema(BaseModel):
    actionList: list[(deposit, int)] = Field(
        description=("Sequence of (deposit, "
                     "NumberOfTimesDepositToBeExecuted)s to be executed "
                     "by the user"))
    stateList: list[state] = Field(
        description=("Sequence of states reached after executing the "
                     "Sequence of deposits"))
    fallShortAmount: float = Field(
        description=("Fall short amount to the goal"))


class OptimalActionFixedDepositToolArgsSchema(BaseModel):
    s0: state = Field(description="Present state of the user")
    sg: state = Field(description="Goal state of the user")
    inflation: float = Field(description="Inflation rate of the country")
    deposits: list[deposit] = Field(
        description="list of popular bank deposit schemes")


@tool(args_schema=OptimalActionFixedDepositToolArgsSchema)
def OptimalActionFixedDepositTool(
        s0, sg, inflation, deposits
) -> OptimalActionFixedDepositToolReturnsSchema:
    """
    Returns list of optimal actions to be followed by the user.
    args:
      s0: Initial state of the user.
      sg: Goal state of the user.
      inflation: inflation rate of the country.
      deposits: list of popular bank deposit schemes.
    """
    # Sorting will speed up the search.
    oA = OptimalActionFixedDeposit(s0, sg, inflation, deposits)
    oA.printActionList()
    actionStateList, fallShortAmount = oA.getActionList()
    if not actionStateList:
        return [], []
    firsts, seconds = map(list, zip(*actionStateList))
    return firsts, seconds, fallShortAmount


class OptimalActionFixedDeposit():
    # Every work of the class is done in the init itself.
    def __init__(self, s0, sg, inflation, deposits):
        self.s0 = s0
        self.sg = sg
        self.inflation = inflation
        self.deposits = sorted(
            deposits, key=lambda x: self.sortBase(x), reverse=True)
        actionStateList1 = []
        self.actionStateList = []
        gS = GoalSearch(self.sg, self.deposits,
                        self._finalBalance, self._reached)
        gS.BestSearch2(state(balance=s0.balance, time=s0.time))   
        actionStateList1, self.fallShortAmount = gS.getFinalList()
        for each in actionStateList1:
            self.actionStateList.append(((self.deposits[each[0][0]], each[0][1]), each[1]))

    def getActionList(self):
        return self.actionStateList, self.fallShortAmount

    def printActionList(self):
        pprint('Initial state')
        pprint(self.s0)
        pprint('Action list')
        pprint(self.actionStateList)
        pprint('Goal state')
        pprint(self.sg)

    def _reached(self, s, sg):
        if s.time <= sg.time:
            retVal = GOAL_NOT_YET_REACHED
        else:
            retVal = GOAL_NOT_REACHABLE
        return retVal

    def sortBase(self, deposit):
        return ((1 + (deposit.interestRate
                      * deposit.compoundingDuration / 100))
                ** ((deposit.duration / deposit.compoundingDuration)
                    * (math.floor(((self.sg.time - self.s0.time).days
                                   / (365 * deposit.duration))))))

    def _finalBalance(self, s, deposit):
        count = (math.floor(
            ((self.sg.time - s.time).days / (365 * deposit.duration))))
        if (0 == count):
            count = 1
        return (state(balance=(s.balance
                               / ((1 + (self.inflation / 100))
                               ** (deposit.duration * count)))
                      * ((1 + (deposit.interestRate
                               * deposit.compoundingDuration / 100))
                         ** ((deposit.duration
                              / deposit.compoundingDuration) * count)),
                      time=s.time + timedelta(
                          days=(deposit.duration * count * 365))),
                count)


class recurringDeposit(BaseModel):
    interestRate: float = Field(
        description="Yearly Interest rate of the recurring deposit in percent")
    duration: float = Field(
        description="total duration of the recurring deposit in years")
    compoundingDuration: float = Field(
        description="Compounding duration of the recurring deposit in years")
    recurringDuration: float = Field(
        description=("time period of the installment of the recurring "
                     "deposit in months"))
    scheme_name: str = Field(
        description="scheme name of the recurring deposit")
    bank_name: str = Field(
        description="bank name of the scheme name of the recurring deposit")


class stateR(BaseModel):
    balance: float = Field(
        description="Present installment planned by the user")
    time: date = Field(description="Present time stamp.")


class OptimalActionRecurringDepositToolReturnsSchema(BaseModel):
    actionList: list[(deposit, int)] = Field(
        description=("Sequence of (deposit, "
                     "NumberOfTimesDepositToBeExecuted)s to be executed "
                     "by the user"))
    stateList: list[state] = Field(
        description=("Sequence of states reached after executing the "
                     "Sequence of deposits"))
    fallShortAmount: float = Field(
        description=("Fall short amount to the goal"))


class OptimalActionRecurringDepositToolArgsSchema(BaseModel):
    s0: stateR = Field(
        description="Present state of the user's planned installment")
    sg: state = Field(description="Goal state of the user")
    inflation: float = Field(description="Inflation rate of the country")
    recurringDeposits: list[recurringDeposit] = Field(description="list of popular bank recurring deposit schemes")
    fixedDeposits: list[deposit] = Field(description="list of popular bank fixed deposit schemes")
    


@tool(args_schema=OptimalActionRecurringDepositToolArgsSchema)
def OptimalActionRecurringDepositTool(
        s0, sg, inflation, recurringDeposits, fixedDeposits
) -> OptimalActionRecurringDepositToolReturnsSchema:
    """
    Returns list of optimal actions to be followed by the user.
    args:
      s0: Initial state of the user's planned installment amount.
      sg: Goal state of the user.
      inflation: inflation rate of the country.
      recurringDeposits: list of popular recurring bank deposit schemes.
      fixedDeposits: list of popular recurring bank fixed deposit schemes.
    """
    # Sorting will speed up the search.
    oA = OptimalActionRecurringDeposit(s0, sg, inflation, recurringDeposits)
    oA.printActionList()
    actionStateList, fallShortAmount = oA.getActionList()
    if not actionStateList:
        return [], []
    firsts, seconds = map(list, zip(*actionStateList))
    
    time1 = s0.time
    sum = 0
    for everyActionState in actionStateList:
        balance1 = everyActionState[1].balance / everyActionState[0][1]        
        time1 = time1 + timedelta(days = (everyActionState[1].time - time1).days / everyActionState[0][1])
        for everyRepeatedAction in range(everyActionState[0][1]):
            tempOA = OptimalActionFixedDeposit(state(balance = balance1, time = time1), sg, 0, fixedDeposits)
            tempActionStateList, _ = tempOA.getActionList()
            if not tempActionStateList:
                break
            tempFirsts , tempSeconds = map(list, zip(*tempActionStateList))
            firsts = firsts + tempFirsts
            seconds = seconds + tempSeconds
            sum = sum + seconds[-1].balance
            
            time1 = time1 + timedelta(days = (everyActionState[1].time - time1).days / everyActionState[0][1])
            
    return firsts, seconds, (fallShortAmount - sum)


class OptimalActionRecurringDeposit():
    # Every work of the class is done in the init itself.
    def __init__(self, s0, sg, inflation, recurringDeposits):
        self.s0 = s0
        self.sg = sg
        self.inflation = inflation
        self.deposits = sorted(
            recurringDeposits, key=lambda x: self.sortBase(x), reverse=True)
        actionStateList1 = []
        self.actionStateList = []
        gS = GoalSearch(self.sg, self.deposits,
                        self._finalBalance, self._reached)
        gS.BestSearch2(state(balance=s0.balance, time=s0.time))
        actionStateList1, self.fallShortAmount = gS.getFinalList()
        for each in actionStateList1:
            self.actionStateList.append(((self.deposits[each[0][0]], each[0][1]), each[1]))
        

    def getActionList(self):
        return self.actionStateList, self.fallShortAmount

    def printActionList(self):
        pprint('Initial installment planned')
        pprint(self.s0)
        pprint('Recurring Action list')
        pprint(self.actionStateList)
        pprint('Goal state')
        pprint(self.sg)

    def _reached(self, s, sg):
        if s.time <= sg.time:
            retVal = GOAL_NOT_YET_REACHED
        else:
            retVal = GOAL_NOT_REACHABLE
        return retVal

    def sortBase(self, deposit):
        ar = (1 + ((deposit.interestRate / 100)*(deposit.compoundingDuration)))
        exp1 = ((deposit.recurringDuration/12)
                     / deposit.compoundingDuration)
        qw1 = ((ar ** exp1) - 1)
        
        exp2 = ((deposit.duration) / deposit.compoundingDuration)
        qw2 = (ar ** exp2) - 1
        
        qw3 = (ar ** exp1)
        w = qw3 * qw2 / qw1
        return w

    # def _finalBalance(self, s, deposit):
    #     ar = (1 + ((deposit.interestRate / 100)*(deposit.compoundingDuration)))
    #     exp1 = ((deposit.recurringDuration/12)
    #                  / deposit.compoundingDuration)
    #     qw1 = ((ar ** exp1) - 1)
        
    #     exp2 = ((deposit.duration) / deposit.compoundingDuration)
    #     qw2 = (ar ** exp2) - 1
        
    #     qw3 = (ar ** exp1)
    #     w = qw3 * qw2 / qw1
    #     return (state(balance=((s.balance
    #                             / ((1 + (self.inflation / 100))
    #                             ** (deposit.duration)))
    #                            * w),
    #                   time=s.time + timedelta(
    #                       days=(deposit.duration * 365))), 1)
        
    def _finalBalance(self, s, deposit):
        count = (math.floor(
            ((self.sg.time - s.time).days / (365 * deposit.duration))))
        if (0 == count):
            count = 1
        ar = (1 + ((deposit.interestRate / 100)*(deposit.compoundingDuration)))
        exp1 = ((deposit.recurringDuration/12)
                     / deposit.compoundingDuration)
        qw1 = ((ar ** exp1) - 1)
        
        exp2 = ((deposit.duration) / deposit.compoundingDuration)
        qw2 = (ar ** exp2) - 1
        
        qw3 = (ar ** exp1)
        w = qw3 * qw2 / qw1
        return (state(balance=((s.balance
                                / ((1 + (self.inflation / 100))
                                ** (deposit.duration * count)))
                               * w * count),
                      time=s.time + timedelta(
                          days=(deposit.duration * count * 365))), count)        


class ParallelDepositsStateValueAtEndReturnsSchema(BaseModel):
    s: state = Field(description="End state of 2 parallel deposit sequences.")


class ParallelDepositsStateValueAtEndArgsSchema(BaseModel):
    s0: state = Field(description="Present state of the user's state")
    sEnd1: state = Field(
        description=("Early reached end state of sequence of fixed deposits "
                     "of the user"))
    sEnd2: state = Field(
        description=("Early reached end state of sequence of recurring "
                     "deposits of the user"))
    inflation: float = Field(description="Inflation rate of the country")


@tool(args_schema=ParallelDepositsStateValueAtEndArgsSchema)
def ParallelDepositsStateValueAtEnd(s0, s1, s2, inflation):
    """
    Returns the Value of the combined parallel 2 deposit sequences
    args:
      s0: Initial state of the user.
      s1: Early reached end state of sequence of fixed deposits of the user
      s2: Early reached end state of sequence of recurring deposits of the user
      inflation: inflation rate of the country.
    """
    v1 = s1.balance * (1 + inflation * (s1.time - s0.time).days/(365 * 100))
    v2 = s2.balance * (1 + inflation * (s2.time - s0.time).days/(365 * 100))
    maxDuration = max((s1.time - s0.time).days, (s2.time - s0.time).days)
    v = (v1 + v2) / maxDuration
    return state(balance=v, time=s0.time + timedelta(days=maxDuration))
