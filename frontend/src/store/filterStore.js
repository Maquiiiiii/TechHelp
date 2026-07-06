import { create } from 'zustand';

export const useFilterStore = create((set) => ({
  // Filtros de lista de entradas
  ticketSearch: '',
  ticketPriority: '',
  ticketStatus: '',
  ticketCategory: '',
  
  setTicketSearch: (search) => set({ ticketSearch: search }),
  setTicketPriority: (priority) => set({ ticketPriority: priority }),
  setTicketStatus: (status) => set({ ticketStatus: status }),
  setTicketCategory: (category) => set({ ticketCategory: category }),
  resetTicketFilters: () => set({
    ticketSearch: '',
    ticketPriority: '',
    ticketStatus: '',
    ticketCategory: ''
  }),

  // Filtros de organización
  orgSearch: '',
  setOrgSearch: (search) => set({ orgSearch: search }),

  // Filtros técnicos
  techEspecialidad: '',
  setTechEspecialidad: (especialidad) => set({ techEspecialidad: especialidad }),
  resetTechFilters: () => set({ techEspecialidad: '' })
}));

export default useFilterStore;