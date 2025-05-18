const { ApolloServer } = require('@apollo/server');
const { startStandaloneServer } = require('@apollo/server/standalone');
const fetch = require('cross-fetch');

const typeDefs = `
  type Order {
    id: Int
    product_id: Int
    user_id: Int
    quantity: Int
    status: String
    product: Product
    user: User
  }
  type Product {
    id: Int
    name: String
    price: Float
  }
  type User {
    id: Int
    name: String
    email: String
  }
  type Query {
    order(id: Int!): Order
  }
`;

const resolvers = {
  Query: {
    order: async (_, { id }) => {
      // Fetch order from the gateway service (which should be extended to support GET /orders/:id)
      const orderRes = await fetch(`http://localhost:5001/orders/${id}`);
      if (!orderRes.ok) return null;
      const order = await orderRes.json();

      // For demo, mock product and user data (since product/user services do not expose GET by id)
      const product = {
        id: order.product_id,
        name: 'Sample Product',
        price: 99.99
      };
      const user = {
        id: order.user_id,
        name: 'Sample User',
        email: 'user@example.com'
      };

      return { ...order, product, user };
    }
  }
};

async function start() {
  const server = new ApolloServer({ typeDefs, resolvers });
  const { url } = await startStandaloneServer(server, { listen: { port: 4000 } });
  console.log(`🚀 GraphQL Gateway ready at ${url}`);
}

start();