import numpy as np
import os
import random
import uuid
from peer import *
from transaction import *
from block import *
from graph import *
from queue import PriorityQueue
import treelib
from treelib import Node, Tree
import networkx as nx
import matplotlib.pyplot as plt
from show import *

def latency(i,j,prop_ij,size):
    c_ij = 5000
    if(i.fast and j.fast):
        c_ij = 100000

    d = np.random.exponential(scale=96/c_ij)
    return prop_ij+((size)/c_ij) + 1000*d


if __name__ == '__main__':
    N = int(input("Enter the number of peers: "))
    Z0 = float(input("fraction of slow peers as Z0: "))
    Z1 = float(input("fraction of low cpu peers peers as Z1: "))
    t_it = float(input("The interarrival between transactions as t_it: "))
    b_it = float(input("The interarrival between blocks as b_it: "))
    BLOCKS = int(input("Total no of Blocks to create: "))

    edges = None
    while True:
        edges = create_graph(N)
        if(connected(edges)):
            break

    for i in range(N):
        print(i,":",edges[i])

    N_slow = int(N*Z0)
    N_low_cpu = int(N*Z1)
    slow_hash_power = float(1/(10*N-9*N_slow))
    uid = 0

    slow_peers = random.sample(range(N), N_slow)
    low_cpu_peers = random.sample(range(N), N_low_cpu)

    peers = []
    start_amount = []
    for i in range(N):
        peers.append(Peer(i, i not in slow_peers, i not in low_cpu_peers, edges[i]))
        start_amount.append(float(1000))


    prop_ij = [[0 for j in range(N)] for i in range(N)]

    for i in range(N):
        for j in range(N):
            prop_ij[i][j] = np.random.uniform(10,500)

    peer_blocks = [[] for _ in range(N)]
    peer_pending_block_queue = [[] for _ in range(N)]
    peer_transactions = [[] for _ in range(N)]
    peer_transactions_unspent = [[] for _ in range(N)]


    current_time = float(0)


    genisis_block = Block(uid,-1,-1,0,current_time,start_amount)
    uid+=1
    for i in range(N):
        peer_blocks[i].append(genisis_block)

    # there are 4 type of events
    # create transaction [time,0,sender,null,null,-1,starttime]
    # create block [time,1,sender,null,parent_id,null,-1,starttime]
    # receive transaction [time,2,sender,null,transaction,receiver,starttime]
    # receive block [time,3,sender,block,null,receiver,starttime]

    event_queue = PriorityQueue()

    for i in range(N):
        delay = np.random.exponential(scale=t_it)
        task = [current_time+delay,0,i,None,None,-1,current_time]
        event_queue.put(task)

    for i in range(N):

        power = None
        if peers[i].type:
            power = slow_hash_power*10
        else:
            power = slow_hash_power


        delay = np.random.exponential(scale=b_it/power)
        task = [current_time+delay,1,i,None,genisis_block.block_id,None,-1,current_time]
        event_queue.put(task)

    created_blocks = 0


    while (not event_queue.empty()):
        # create blocks till BLOCKS are created
        # create transactions till BLOCKS are created
        # receive transactions and blocks will be done till the end of the simulation
        event = event_queue.get()
        current_time = event[0]
        event_type = event[1]
        



        if event_type == 0:
            if created_blocks == BLOCKS:
                print("All blocks are created")
                continue
            print("Create transaction")
            sender = event[2]
            possible_recievers = [i for i in range(N) if i != sender]
            receiver = random.choice(possible_recievers)
            # find longest block in recieved blocks 
            max_length = -1
            longest_block = None
            for b in peer_blocks[sender]:
                if b.length > max_length:
                    max_length = b.length
                    longest_block = b

            

            # find the balance of sender in longest block
            amount = longest_block.balances[sender]

            pay = random.random()
            if pay > amount:
                print("Insufficient balance")
                continue
            
            transac_id = uid
            uid+=1
            new_transac = transaction(transac_id,sender,receiver,pay,8000)
            # as it is new add into both Transaction lists
            peer_transactions[sender].append(new_transac)
            peer_transactions_unspent[sender].append(new_transac)


            # create a next create transaction event
            delay = np.random.exponential(scale=t_it)
            task = [current_time+delay,0,sender,None,None,-1,current_time]
            event_queue.put(task)

            # create a receive transaction event for all its neighbours except sender
            for i in edges[sender]:
                delay = latency(peers[sender],peers[i],prop_ij[sender][i],8000)
                task = [current_time+delay,2,sender,None,new_transac,i,current_time]
                event_queue.put(task)


            

        elif event_type == 1:
            if created_blocks == BLOCKS:
                continue

            print("Create block")
            # check if longest block is still parent_id in the event else continue
            sender = event[2]
            parent_id = event[4]
            max_length = -1
            longest_block = None
            for b in peer_blocks[sender]:
                if b.length > max_length:
                    max_length = b.length
                    longest_block = b
                elif b.length == max_length and b.time < longest_block.time:
                    longest_block = b

            if longest_block.block_id != parent_id:
                print("Discarded create block event")
                continue 

            # randomly sample atmost 999 transactions from peer_transactions_unspent[sender]
            transactions = random.sample(peer_transactions_unspent[sender],min(999,len(peer_transactions_unspent[sender])))
            # craete a copy of balances of longest block
            balances = longest_block.balances.copy()
            # create a coin base transaction
            coin_base = transaction(uid,-1,sender,50,8000)
            uid+=1
            transactions.append(coin_base)
            # update the balances
            balances[sender] += 50
            for tran in transactions:
                if tran.idx != -1:
                    balances[tran.idx] -= tran.amount
                    balances[tran.idy] += tran.amount

            # check if the balances are valid
            valid = True
            for i in range(N):
                if balances[i] < 0:
                    valid = False
                    break

            if not valid:
                print("invalid block created")
                continue

            # update the unspent transactions of sender
            new_unspent = []
            for tran in peer_transactions_unspent[sender]:
                found = False
                for t in transactions:
                    if t.transaction_id == tran.transaction_id:
                        found = True
                        break
                if not found:
                    new_unspent.append(tran)

            peer_transactions_unspent[sender] = new_unspent

            # create a new block
            print("block is created at length ",longest_block.length+1)
            new_block = Block(uid,parent_id,sender,longest_block.length+1,current_time,balances)
            uid+=1
            new_block.transactions = transactions.copy()
            # print(len(new_block.transactions))

            # add this block to peer_blocks[sender]
            peer_blocks[sender].append(new_block)
            created_blocks+=1

            # broadcast this block to all its neighbours
            for i in edges[sender]:
                delay = latency(peers[sender],peers[i],prop_ij[sender][i],8000*len(transactions))
                task = [current_time+delay,3,sender,new_block,None,i,current_time]
                event_queue.put(task)

            

            
            



        elif event_type == 2:
            # check if transaction is there in the pper_transactions[receiver]
            found = False
            receiver = event[5]
            r_transaction = event[4]
            for transac in peer_transactions[receiver]:
                if transac.transaction_id == r_transaction.transaction_id:
                    found = True
                    break
            
            # if not found send this transactions to all its neightbouts except sender
            if not found:
                print("Receive transaction")

                new_transac = transaction(r_transaction.transaction_id,r_transaction.idx,r_transaction.idy,r_transaction.amount,r_transaction.size)
                peer_transactions[receiver].append(new_transac)
                # add int unspent if it is not in peer_blocks[receiver]
                is_spent = False
                for block in peer_blocks[receiver]:
                    for tran in block.transactions:
                        if tran.transaction_id == new_transac.transaction_id:
                            is_spent = True
                            break
                
                if not is_spent:
                    peer_transactions_unspent[receiver].append(new_transac)

                for i in edges[receiver]:
                    if i == event[2]:
                        continue
                    delay = latency(peers[receiver],peers[i],prop_ij[receiver][i],8000)
                    task = [current_time+delay,2,receiver,None,new_transac,i,current_time]
                    event_queue.put(task)




    
        elif event_type == 3:
            # check if block is there in the peer_blocks[receiver]
            # event structure [time,3,sender,block,null,receiver,starttime]
            print("Receive block")
            found = False
            receiver = event[5]
            r_block = Block(event[3].block_id,event[3].prev_block_id,event[3].miner_id,event[3].length,event[3].time,event[3].balances)
            r_block.transactions = event[3].transactions.copy()
            for block in peer_blocks[receiver]:
                if block.block_id == r_block.block_id:
                    found = True
                    break
            
            if found:
                print("Block is already received")
                continue

            # find parent block of the r_block
            parent_block = None
            for block in peer_blocks[receiver]:
                if block.block_id == r_block.prev_block_id:
                    parent_block = block
                    break

            if parent_block == None:
                print("Parent block not found")
                # add this block to pending block queue if not already present
                found = False
                for block in peer_pending_block_queue[receiver]:
                    if block.block_id == r_block.block_id:
                        found = True
                        break
                if found:
                    continue
                # add this block to pending block queue
                peer_pending_block_queue[receiver].append(r_block)
                # send it to all its neighbours except sender
                for i in edges[receiver]:
                    if i == event[2]:
                        continue
                    delay = latency(peers[receiver],peers[i],prop_ij[receiver][i],8000*len(r_block.transactions))
                    task = [current_time+delay,3,receiver,r_block,None,i,current_time]
                    event_queue.put(task)
                # do nothing
                continue

            else:
                #update unspent transactions of receiver
                new_unspent = []
                for tran in peer_transactions_unspent[receiver]:
                    found = False
                    for t in r_block.transactions:
                        if t.transaction_id == tran.transaction_id:
                            found = True
                            break
                    if not found:
                        new_unspent.append(tran)
                peer_transactions_unspent[receiver] = new_unspent
                peer_blocks[receiver].append(r_block)
                # send it to all its neighbours except sender
                for i in edges[receiver]:
                    if i == event[2]:
                        continue
                    delay = latency(peers[receiver],peers[i],prop_ij[receiver][i],8000*len(r_block.transactions))
                    task = [current_time+delay,3,receiver,r_block,None,i,current_time]
                    event_queue.put(task)

            # update the pending block queue of receiver
            while True:
                # check if r_block is parent of any block in pending block queue
                found = False
                check_block = None
                for block in peer_pending_block_queue[receiver]:
                    if block.prev_block_id == r_block.block_id:
                        found = True
                        check_block = block
                        break
                if not found:
                    break
                # remove the block from pending block queue
                peer_pending_block_queue[receiver].remove(check_block)
                # add this block to peer_blocks[receiver]
                peer_blocks[receiver].append(check_block)
                # update the unspent transactions of receiver
                new_unspent = []
                for tran in peer_transactions_unspent[receiver]:
                    found = False
                    for t in check_block.transactions:
                        if t.transaction_id == tran.transaction_id:
                            found = True
                            break
                    if not found:
                        new_unspent.append(tran)
                peer_transactions_unspent[receiver] = new_unspent
                # copy check block to r_block
                r_block = Block(check_block.block_id,check_block.prev_block_id,check_block.miner_id,check_block.length,check_block.time,check_block.balances)
                r_block.transactions = check_block.transactions.copy()

            # find the longest block of receiver
            max_length = -1
            longest_block = None
            for b in peer_blocks[receiver]:
                if b.length > max_length:
                    max_length = b.length
                    longest_block = b
                elif b.length == max_length and b.time < longest_block.time:
                    longest_block = b
            
            # create a new create block event for receiver
            power = None
            if peers[receiver].type:
                power = slow_hash_power*10
            else:
                power = slow_hash_power
            


            delay = np.random.exponential(scale=b_it/power)
            task = [current_time+delay,1,receiver,None,longest_block.block_id,None,-1,current_time]
            event_queue.put(task)





            





        else:
            print("Invalid event type")
            break

    # print all the received blocks of each peer in output_peerid.txt file 
    for i in range(N):
        filename = "output_peer" + str(i) + ".txt"
        # remove the file if it already exists
        if os.path.exists(filename):
            os.remove(filename)
        f = open(filename,"w")
        for block in peer_blocks[i]:
            f.write("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n")
            f.write("Block ID: " + str(block.block_id) + "\n")
            f.write("Previous Block ID: " + str(block.prev_block_id) + "\n")
            f.write("Miner ID: " + str(block.miner_id) + "\n")
            f.write("Length: " + str(block.length) + "\n")
            f.write("Time: " + str(block.time) + "\n")
            f.write("Balances: " + str(block.balances) + "\n")
            f.write("No of Transactions: "+str(len(block.transactions))+" \n")
            f.write("Transactions: \n")
            for tran in block.transactions:
                f.write("Transaction ID: " + str(tran.transaction_id) + "\n")
                f.write("Sender: " + str(tran.idx) + "\n")
                f.write("Receiver: " + str(tran.idy) + "\n")
                f.write("Amount: " + str(tran.amount) + "\n")
                f.write("Size: " + str(tran.size) + "\n")
            f.write("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n")
        f.close()


    # finally create the block tree of each peer using the graphviz library
    # source : https://graphviz.readthedocs.io/en/stable/manual.html
    for i in range(N):
        node_edges = []
        for block in peer_blocks[i]:
            if block.prev_block_id == -1:
                continue
            node_edges.append([block.prev_block_id,block.block_id])
        
        tree = build_tree(node_edges)
        # delete the file if it already exists
        tree.attr('node', shape='circle', width='0.1', height='0.1')  # Adjust node size
        tree.attr('edge', minlen='1') 
        if os.path.exists("output_peer"+str(i)+".png"):
            os.remove("output_peer"+str(i)+".png")
        tree.render("output_peer"+str(i),format='png',cleanup=True)


    # for each peer find percentage of longest chain length to total blocks
    for i in range(N):
        max_length = -1
        for block in peer_blocks[i]:
            if block.length > max_length:
                max_length = block.length
        print("Peer ",i," longest chain length: ",max_length+1)
        print("Peer ",i," percentage of longest chain length to total blocks: ",((max_length+1)/(BLOCKS+1))*100)


        



        
    



