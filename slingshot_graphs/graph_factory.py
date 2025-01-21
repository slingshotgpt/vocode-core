import asyncio
import os 

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage
)

from call_config import CallConfig
from langgraph.checkpoint.memory import MemorySaver

from slingshot_graphs.default_graph import DefaultGraph

class GraphManager:
    _instance = None
    _graph = None 
    _memory = None 
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GraphManager, cls).__new__(cls)
            cls._instance._initialize_graph()
        return cls._instance 
    
    def _initialize_graph(self):
        if self._memory is None:
            self._memory = MemorySaver()

        graph_config = {
            "default": DefaultGraph
        }

        client_name = CallConfig().client_name or 'default'
        graph_class = graph_config.get(client_name)
        
        print(f"Initializing {graph_class.__name__}")
        self._graph = graph_class().get_graph()
        self.graph.checkpointer = self._memory
    
    @property
    def graph(self):
        return self._graph 
    
    def reinitialize_graph(self, clear_memory=True):
        if clear_memory:
            self._memory = None 
        self._initialize_graph()
        print("Graph has been reinitialized")